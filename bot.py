#!/usr/bin/env python3
"""Bot absen otomatis untuk Gosh Live."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

from gosh_client import GoshClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gosh-bot")


def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config tidak ditemukan: {path}\n"
            "Salin config.example.json ke config.json lalu isi data login."
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


def _extract_comment_text(text_data: dict) -> str | None:
    """Ambil teks komentar, termasuk emoji custom Gosh ([emoji:id])."""
    text = (text_data.get("text") or "").strip()
    rich = text_data.get("rich_content") or []

    if text and "[emoji:" not in text:
        return text

    if rich:
        parts: list[str] = []
        for item in rich:
            item_type = item.get("type")
            if item_type == "text":
                part = (item.get("text") or "").strip()
                if part:
                    parts.append(part)
            elif item_type == "emoji":
                emoji_id = item.get("emoji_id")
                parts.append(f"[emoji:{emoji_id}]" if emoji_id else "[emoji]")
        if parts:
            return "".join(parts)

    if text:
        return text

    return None


def parse_chat_message(raw_msg: dict) -> dict | None:
    payload = raw_msg.get("payload") or {}
    data_str = payload.get("data")
    if not data_str:
        return None

    try:
        inner = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    if inner.get("type") != 10000:
        return None

    user = inner.get("user") or {}
    text_data = inner.get("data") or {}
    text = _extract_comment_text(text_data)
    if not text:
        return None

    return {
        "user_id": str(user.get("id") or raw_msg.get("from") or ""),
        "nickname": user.get("nickname") or "unknown",
        "text": text,
        "sequence": raw_msg.get("sequence"),
        "bot_type": user.get("bot_type", 0),
        "live_id": str(inner.get("live_id") or ""),
        "is_emoji": bool(re.search(r"\[emoji:\d+\]", text)),
    }


def ensure_login(client: GoshClient, config: dict, cookies_file: str) -> None:
    login_cfg = config.get("login") or {}
    email = login_cfg.get("email", "").strip()
    password = login_cfg.get("password", "").strip()
    sm_box_id = (config.get("sm_box_id") or login_cfg.get("sm_box_id") or "").strip()

    if client.uid:
        log.info("Sudah login (uid=%s)", client.uid)
        return

    if not email or not password:
        raise RuntimeError(
            "Isi email dan password di config.json bagian login."
        )

    log.info("Login dengan email %s ...", email)
    client.login(email, password, sm_box_id=sm_box_id or None)
    client.save_cookies(cookies_file)
    log.info("Login berhasil (uid=%s). Sesi disimpan ke %s", client.uid, cookies_file)


def get_commenter_chat_target(
    client: GoshClient,
    commenter_id: str,
) -> tuple[str, str] | None:
    room = client.get_commenter_room(commenter_id)
    return client.resolve_chat_target(room, commenter_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gosh Live bot absen otomatis")
    parser.add_argument("-c", "--config", default="config.json", help="Path config JSON")
    args = parser.parse_args()

    config = load_config(args.config)
    anchor_id = str(config["anchor_id"])
    reply_message = config.get("reply_message", "absen kak, hadir")
    poll_interval = float(config.get("poll_interval_seconds", 3))
    cooldown = float(config.get("cooldown_per_user_seconds", 300))
    skip_bots = bool(config.get("skip_bot_accounts", False))
    verbose = bool(config.get("verbose_polling", False))
    cookies_file = config.get("cookies_file", "cookies.json")

    login_cfg = config.get("login") or {}
    use_saved_session = bool(config.get("use_saved_session", False))
    has_credentials = bool(
        login_cfg.get("email", "").strip() and login_cfg.get("password", "").strip()
    )

    client = GoshClient(
        cookies_file=cookies_file if use_saved_session else None,
        load_cookies=use_saved_session,
    )
    ensure_login(client, config, cookies_file)

    processed_sequences: set[int | str] = set()
    last_reply_at: dict[str, float] = {}

    log.info("Siap pantau komen baru")

    log.info("Memantau komentar https://gosh.com/%s", anchor_id)
    log.info("Balasan otomatis: %r", reply_message)
    log.info(
        "Mode: selalu absen di profil/live penonton yang komen "
        "(stream kamu online/offline tetap jalan)"
    )
    log.info("Tekan Ctrl+C untuk berhenti.")

    while True:
        try:
            data = client.fetch_messages(anchor_id)
            msgs = data.get("msgs") or []
            if verbose and not msgs:
                log.info("Polling... belum ada komen baru")

            for raw_msg in msgs:
                sequence = raw_msg.get("sequence")
                if sequence in processed_sequences:
                    continue
                processed_sequences.add(sequence)

                parsed = parse_chat_message(raw_msg)
                if not parsed:
                    if verbose:
                        log.info("Lewati pesan non-komentar seq=%s", sequence)
                    continue

                commenter_id = parsed["user_id"]
                if not commenter_id:
                    continue
                if commenter_id == str(client.uid):
                    if verbose:
                        log.info("Lewati komen sendiri seq=%s", sequence)
                    continue
                if skip_bots and parsed.get("bot_type") == 1:
                    log.info(
                        "Lewati %s — skip_bot_accounts aktif (bot_type=%s)",
                        parsed["nickname"],
                        parsed.get("bot_type"),
                    )
                    continue

                now = time.time()
                if now - last_reply_at.get(commenter_id, 0) < cooldown:
                    continue

                log.info(
                    "Komentar baru dari %s (%s): %s",
                    parsed["nickname"],
                    commenter_id,
                    parsed["text"],
                )

                target = get_commenter_chat_target(client, commenter_id)
                if not target:
                    log.info(
                        "%s sedang offline / tidak punya live aktif, lewati.",
                        parsed["nickname"],
                    )
                    continue
                group_id, live_id = target

                try:
                    client.send_chat_message(
                        commenter_id,
                        live_id,
                        reply_message,
                        group_id=group_id,
                    )
                    last_reply_at[commenter_id] = now
                    log.info(
                        "Berhasil absen di profil %s (%s)",
                        parsed["nickname"],
                        commenter_id,
                    )
                except Exception as exc:
                    log.error("Gagal kirim ke %s: %s", parsed["nickname"], exc)

            wait_ms = data.get("next_internal_millis") or int(poll_interval * 1000)
            time.sleep(max(wait_ms, 1000) / 1000)

        except KeyboardInterrupt:
            log.info("Bot dihentikan.")
            return 0
        except Exception as exc:
            log.error("Error: %s", exc)
            time.sleep(poll_interval)


if __name__ == "__main__":
    sys.exit(main())
