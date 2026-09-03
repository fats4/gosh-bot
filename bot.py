#!/usr/bin/env python3
"""Bot absen otomatis untuk Gosh Live."""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from gosh_client import GoshApiError, GoshClient, RATE_LIMIT_CODE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gosh-bot")

DEFAULT_REPLY_TEMPLATES = (
    "absen kak, hadir dari {from_name}",
    "wak hadir bang, absen dari {from_name}",
    "hadir kak, absen {from_name}",
    "absen kak, {from_name} hadir",
    "hadir bang, absen dari {from_name} ya",
    "absen kak, izin hadir dari {from_name}",
    "hadir kak, absen dari {from_name} nih",
    "absen bang, {from_name} hadir",
    "wak absen kak, hadir dari {from_name}",
    "hadir bang, {from_name} absen",
)

ACCOUNT_KEYS = (
    "name",
    "anchor_id",
    "reply_message",
    "reply_from_name",
    "randomize_reply",
    "reply_messages",
    "poll_interval_seconds",
    "cooldown_per_user_seconds",
    "skip_bot_accounts",
    "skip_fleet_accounts",
    "auto_follow_on_comment",
    "watch_before_comment_seconds",
    "boost_own_live_viewers",
    "reply_stagger_min_seconds",
    "reply_stagger_max_seconds",
    "rate_limit_retry_min_seconds",
    "rate_limit_retry_max_seconds",
    "min_poll_interval_seconds",
    "verbose_polling",
    "use_saved_session",
    "sm_box_id",
    "proxy",
    "login",
    "cookies_file",
)


def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config tidak ditemukan: {path}\n"
            "Salin config.example.json ke config.json lalu isi data login."
        )
    return json.loads(config_path.read_text(encoding="utf-8"))


def _merge_account(global_cfg: dict, account_cfg: dict, index: int) -> dict:
    """Gabungkan setting global dengan override per akun."""
    merged: dict[str, Any] = {}
    for key in ACCOUNT_KEYS:
        if key in account_cfg and account_cfg[key] is not None:
            merged[key] = account_cfg[key]
        elif key in global_cfg and global_cfg[key] is not None:
            merged[key] = global_cfg[key]

    name = str(merged.get("name") or f"acc{index + 1}").strip()
    merged["name"] = name

    anchor_id = str(merged.get("anchor_id") or "").strip()
    if not anchor_id:
        raise ValueError(f"Akun '{name}': anchor_id wajib diisi.")
    merged["anchor_id"] = anchor_id

    login_cfg = merged.get("login") or {}
    email = str(login_cfg.get("email") or "").strip()
    password = str(login_cfg.get("password") or "").strip()
    if not email or not password:
        raise ValueError(f"Akun '{name}': login.email dan login.password wajib diisi.")
    merged["login"] = {"email": email, "password": password}

    merged.setdefault("reply_message", "absen kak, hadir")
    merged.setdefault("reply_from_name", "Faats [KNJ 05]")
    merged.setdefault("randomize_reply", True)
    merged.setdefault("reply_messages", None)
    merged.setdefault("poll_interval_seconds", 0)
    merged.setdefault("cooldown_per_user_seconds", 0)
    merged.setdefault("skip_bot_accounts", False)
    merged.setdefault("skip_fleet_accounts", True)
    merged.setdefault("auto_follow_on_comment", True)
    merged.setdefault("watch_before_comment_seconds", 15)
    merged.setdefault("boost_own_live_viewers", True)
    merged.setdefault("reply_stagger_min_seconds", 5)
    merged.setdefault("reply_stagger_max_seconds", 15)
    merged.setdefault("rate_limit_retry_min_seconds", 15)
    merged.setdefault("rate_limit_retry_max_seconds", 30)
    merged.setdefault("min_poll_interval_seconds", 0)
    merged.setdefault("verbose_polling", False)
    merged.setdefault("use_saved_session", False)
    merged.setdefault("cookies_file", f"cookies_{name}.json")

    sm_box_id = str(merged.get("sm_box_id") or "").strip()
    if not sm_box_id:
        raise ValueError(
            f"Akun '{name}': sm_box_id wajib diisi (global atau per akun)."
        )
    merged["sm_box_id"] = sm_box_id

    return merged


def resolve_accounts(config: dict) -> list[dict]:
    """Dukung format multi `accounts` atau single-account lama."""
    raw_accounts = config.get("accounts")
    if raw_accounts:
        if not isinstance(raw_accounts, list) or not raw_accounts:
            raise ValueError("Config 'accounts' harus berisi array akun.")
        accounts: list[dict] = []
        for index, account_cfg in enumerate(raw_accounts):
            if account_cfg.get("enabled") is False:
                continue
            accounts.append(_merge_account(config, account_cfg, index))
        if not accounts:
            raise ValueError("Tidak ada akun aktif di config 'accounts'.")
        return accounts

    if not config.get("anchor_id"):
        raise ValueError(
            "Config harus punya 'accounts' (multi) atau 'anchor_id' (single)."
        )
    return [_merge_account(config, config, 0)]


def _reply_templates(account: dict) -> list[str]:
    custom = account.get("reply_messages")
    if isinstance(custom, list) and custom:
        return [str(item).strip() for item in custom if str(item).strip()]
    return list(DEFAULT_REPLY_TEMPLATES)


def pick_reply_message(account: dict) -> str:
    """Pilih pesan absen acak dengan inti dari reply_from_name."""
    from_name = str(account.get("reply_from_name") or "Faats [KNJ 05]").strip()
    if not account.get("randomize_reply", True):
        message = str(account.get("reply_message") or "absen kak, hadir").strip()
        if "{from_name}" in message:
            return message.format(from_name=from_name)
        return message

    template = random.choice(_reply_templates(account))
    if "{from_name}" in template:
        return template.format(from_name=from_name)
    return f"{template} {from_name}".strip()


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


class FleetRegistry:
    """UID semua akun bot dalam satu proses — lewati absen antar bot sendiri."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._uids: set[str] = set()

    def register(self, uid: str) -> None:
        with self._lock:
            self._uids.add(str(uid))

    def contains(self, uid: str) -> bool:
        with self._lock:
            return str(uid) in self._uids


class SharedCommentFeed:
    """Satu poller fetch_msg; setiap akun dapat antrian sendiri (broadcast)."""

    def __init__(self, account_names: list[str]) -> None:
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._queues = {name: deque() for name in account_names}
        self._seen_sequences: set[int | str] = set()

    def push(self, parsed: dict[str, Any], sequence: int | str | None) -> bool:
        if sequence is None:
            return False
        with self._condition:
            if sequence in self._seen_sequences:
                return False
            self._seen_sequences.add(sequence)
            comment = {**parsed, "_sequence": sequence}
            for queue in self._queues.values():
                queue.append(comment)
            self._condition.notify_all()
            return True

    def wait_for_comment(
        self,
        account_name: str,
        stop_event: threading.Event,
        *,
        timeout: float = 0.5,
    ) -> dict[str, Any] | None:
        with self._condition:
            queue = self._queues[account_name]
            while True:
                if queue:
                    return queue.popleft()
                if stop_event.is_set():
                    return None
                self._condition.wait(timeout=timeout)
                if stop_event.is_set():
                    return None


class ReplyStaggerCoordinator:
    """Atur jeda antar akun saat follow + absen ke penonton yang sama."""

    def __init__(
        self,
        account_names: list[str],
        *,
        min_seconds: float,
        max_seconds: float,
    ) -> None:
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self.enabled = max_seconds > 0 and len(account_names) > 1
        self._order = {name: index for index, name in enumerate(account_names)}
        self._gates: dict[str, _CommenterReplyGate] = {}
        self._gates_lock = threading.Lock()

    def _get_gate(self, commenter_id: str) -> "_CommenterReplyGate":
        with self._gates_lock:
            gate = self._gates.get(commenter_id)
            if gate is None:
                gate = _CommenterReplyGate()
                self._gates[commenter_id] = gate
            return gate

    def wait_turn(
        self,
        commenter_id: str,
        account_name: str,
        stop_event: threading.Event,
    ) -> bool:
        if not self.enabled:
            return True

        index = self._order.get(account_name, 0)
        gate = self._get_gate(commenter_id)
        with gate.lock:
            while gate.turn < index:
                if stop_event.is_set():
                    return False
                gate.condition.wait(timeout=0.2)

            if index > 0:
                delay = random.uniform(self.min_seconds, self.max_seconds)
                log.info(
                    "[%s] Jeda %.1fs sebelum aksi (antrian akun ke-%d)",
                    account_name,
                    delay,
                    index + 1,
                )
                if stop_event.wait(delay):
                    if gate.turn == index:
                        gate.turn += 1
                        gate.condition.notify_all()
                    return False
            return True

    def release_turn(self, commenter_id: str, account_name: str) -> None:
        if not self.enabled:
            return

        index = self._order.get(account_name, 0)
        gate = self._get_gate(commenter_id)
        with gate.lock:
            if gate.turn == index:
                gate.turn += 1
                gate.condition.notify_all()


class _CommenterReplyGate:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.turn = 0


class AccountBot:
    def __init__(
        self,
        account: dict,
        comment_feed: SharedCommentFeed | None = None,
        reply_stagger: ReplyStaggerCoordinator | None = None,
        fleet_registry: FleetRegistry | None = None,
    ) -> None:
        self.account = account
        self.name = account["name"]
        self.comment_feed = comment_feed
        self.fleet_registry = fleet_registry
        self.anchor_id = account["anchor_id"]
        self.reply_from_name = str(account.get("reply_from_name") or "Faats [KNJ 05]")
        self.randomize_reply = bool(account.get("randomize_reply", True))
        self.poll_interval = float(account["poll_interval_seconds"])
        self.cooldown = float(account["cooldown_per_user_seconds"])
        self.skip_bots = bool(account["skip_bot_accounts"])
        self.skip_fleet = bool(account.get("skip_fleet_accounts", True))
        self.auto_follow = bool(account["auto_follow_on_comment"])
        self.watch_before_comment = float(account.get("watch_before_comment_seconds") or 0)
        self.boost_own_live_viewers = bool(account.get("boost_own_live_viewers", True))
        self.verbose = bool(account["verbose_polling"])
        self.cookies_file = account["cookies_file"]
        self.use_saved_session = bool(account["use_saved_session"])
        self.reply_stagger = reply_stagger
        self.stagger_min = float(account.get("reply_stagger_min_seconds", 0))
        self.stagger_max = float(account.get("reply_stagger_max_seconds", 0))
        self.rate_limit_retry_min = float(account.get("rate_limit_retry_min_seconds", 15))
        self.rate_limit_retry_max = float(account.get("rate_limit_retry_max_seconds", 30))
        self.min_poll_interval = float(account.get("min_poll_interval_seconds", 0))

        self.client = GoshClient(
            cookies_file=self.cookies_file if self.use_saved_session else None,
            load_cookies=self.use_saved_session,
            proxy=account.get("proxy"),
        )
        self.last_reply_at: dict[str, float] = {}
        self.followed_users: set[str] = set()
        self._own_live_viewer: subprocess.Popen | None = None

    def _log(self, level: int, msg: str, *args: Any) -> None:
        log.log(level, f"[{self.name}] {msg}", *args)

    def _with_rate_limit_retry(
        self,
        action: str,
        func,
        stop_event: threading.Event,
        *,
        max_retries: int = 2,
    ):
        for attempt in range(max_retries + 1):
            try:
                return func()
            except GoshApiError as exc:
                if exc.code != RATE_LIMIT_CODE or attempt >= max_retries:
                    raise
                wait = random.uniform(
                    self.rate_limit_retry_min,
                    self.rate_limit_retry_max,
                ) * (attempt + 1)
                self._log(
                    logging.WARNING,
                    "%s kena rate limit (2008), tunggu %.0fs lalu coba lagi...",
                    action,
                    wait,
                )
                if stop_event.wait(wait):
                    raise GoshApiError(
                        RATE_LIMIT_CODE,
                        f"{action} dibatalkan saat menunggu rate limit",
                    ) from exc

    def ensure_login(self) -> None:
        login_cfg = self.account["login"]
        email = login_cfg["email"]
        password = login_cfg["password"]
        sm_box_id = self.account["sm_box_id"]

        if self.client.uid:
            self._log(logging.INFO, "Sudah login (uid=%s)", self.client.uid)
            return

        self._log(logging.INFO, "Login dengan email %s ...", email)
        self.client.login(email, password, sm_box_id=sm_box_id)
        self.client.save_cookies(self.cookies_file)
        if self.fleet_registry and self.client.uid:
            self.fleet_registry.register(self.client.uid)
        self._log(
            logging.INFO,
            "Login berhasil (uid=%s). Sesi disimpan ke %s",
            self.client.uid,
            self.cookies_file,
        )

    def get_commenter_chat_target(self, commenter_id: str) -> tuple[str, str] | None:
        room = self.client.get_commenter_room(commenter_id)
        return self.client.resolve_chat_target(room, commenter_id)

    def get_commenter_room(self, commenter_id: str) -> dict[str, Any] | None:
        return self.client.get_commenter_room(commenter_id)

    def log_startup(self) -> None:
        self._log(logging.INFO, "Memantau komentar https://gosh.com/%s", self.anchor_id)
        if self.client.proxy:
            proxy_host = self.client.proxy.split("@")[-1].split("://")[-1]
            self._log(logging.INFO, "Proxy: %s", proxy_host)
        if self.randomize_reply:
            templates = _reply_templates(self.account)
            self._log(
                logging.INFO,
                "Balasan acak dari %r (%d variasi)",
                self.reply_from_name,
                len(templates),
            )
        else:
            self._log(
                logging.INFO,
                "Balasan tetap: %r",
                pick_reply_message(self.account),
            )
        if self.auto_follow:
            self._log(logging.INFO, "Auto-follow penonton yang komen: aktif")
        else:
            self._log(logging.INFO, "Auto-follow penonton yang komen: nonaktif")
        if self.watch_before_comment > 0:
            self._log(
                logging.INFO,
                "Nonton live dulu %.0fs sebelum absen (browser)",
                self.watch_before_comment,
            )
        if self.boost_own_live_viewers:
            self._log(logging.INFO, "Boost penonton live sendiri: aktif")
        if self.cooldown > 0:
            self._log(logging.INFO, "Cooldown per user: %ss", int(self.cooldown))
        else:
            self._log(logging.INFO, "Cooldown: nonaktif")
        if self.poll_interval > 0:
            self._log(logging.INFO, "Interval polling: %ss", self.poll_interval)
        else:
            self._log(logging.INFO, "Polling: tanpa delay")
        if self.reply_stagger and self.reply_stagger.enabled:
            self._log(
                logging.INFO,
                "Jeda antar akun: %.0f-%.0fs",
                self.stagger_min,
                self.stagger_max,
            )

    def _handle_comment(self, parsed: dict[str, Any], stop_event: threading.Event) -> None:
        commenter_id = parsed["user_id"]
        if not commenter_id:
            return
        if commenter_id == str(self.client.uid):
            if self.verbose:
                self._log(
                    logging.INFO,
                    "Lewati komen sendiri seq=%s",
                    parsed.get("_sequence"),
                )
            return
        if commenter_id == self.anchor_id:
            if self.verbose:
                self._log(
                    logging.INFO,
                    "Lewati komen anchor/live sendiri seq=%s",
                    parsed.get("_sequence"),
                )
            return
        if (
            self.skip_fleet
            and self.fleet_registry
            and self.fleet_registry.contains(commenter_id)
        ):
            if self.verbose:
                self._log(
                    logging.INFO,
                    "Lewati komen akun bot fleet seq=%s dari %s",
                    parsed.get("_sequence"),
                    parsed["nickname"],
                )
            return
        if self.skip_bots and parsed.get("bot_type") == 1:
            self._log(
                logging.INFO,
                "Lewati %s — skip_bot_accounts aktif (bot_type=%s)",
                parsed["nickname"],
                parsed.get("bot_type"),
            )
            return

        self._log(
            logging.INFO,
            "Komentar baru dari %s (%s): %s",
            parsed["nickname"],
            commenter_id,
            parsed["text"],
        )

        stagger = self.reply_stagger
        if stagger and not stagger.wait_turn(commenter_id, self.name, stop_event):
            return

        try:
            if self.auto_follow and commenter_id not in self.followed_users:
                try:
                    self._with_rate_limit_retry(
                        "Follow",
                        lambda: self.client.follow_user(commenter_id),
                        stop_event,
                    )
                    self.followed_users.add(commenter_id)
                    self._log(
                        logging.INFO,
                        "Berhasil follow %s (%s)",
                        parsed["nickname"],
                        commenter_id,
                    )
                except GoshApiError as exc:
                    self._log(
                        logging.WARNING,
                        "Gagal follow %s: %s",
                        parsed["nickname"],
                        exc,
                    )
                except Exception as exc:
                    self._log(
                        logging.WARNING,
                        "Gagal follow %s: %s",
                        parsed["nickname"],
                        exc,
                    )

            now = time.time()
            if (
                self.cooldown > 0
                and now - self.last_reply_at.get(commenter_id, 0) < self.cooldown
            ):
                return

            room = self.get_commenter_room(commenter_id)
            target = self.client.resolve_chat_target(room, commenter_id)
            if not target:
                self._log(
                    logging.INFO,
                    "%s sedang offline / tidak punya live aktif, lewati.",
                    parsed["nickname"],
                )
                return
            group_id, live_id = target

            if self.watch_before_comment > 0:
                if room:
                    self._log(
                        logging.INFO,
                        "Menonton live %s selama %.0fs sebelum absen...",
                        parsed["nickname"],
                        self.watch_before_comment,
                    )
                    self.client.watch_live(
                        room,
                        group_id=group_id,
                        live_id=live_id,
                        anchor_id=commenter_id,
                        seconds=self.watch_before_comment,
                        stop_event=stop_event,
                    )
                elif stop_event.wait(self.watch_before_comment):
                    return

            reply_text = pick_reply_message(self.account)
            self._with_rate_limit_retry(
                "Absen",
                lambda: self.client.send_chat_message(
                    commenter_id,
                    live_id,
                    reply_text,
                    group_id=group_id,
                ),
                stop_event,
            )
            self.last_reply_at[commenter_id] = now
            self._log(
                logging.INFO,
                "Berhasil absen di profil %s (%s): %s",
                parsed["nickname"],
                commenter_id,
                reply_text,
            )
        except GoshApiError as exc:
            self._log(
                logging.ERROR,
                "Gagal absen ke %s: %s",
                parsed["nickname"],
                exc,
            )
        except Exception as exc:
            self._log(
                logging.ERROR,
                "Gagal kirim ke %s: %s",
                parsed["nickname"],
                exc,
            )
        finally:
            if stagger:
                stagger.release_turn(commenter_id, self.name)

    def _start_own_live_viewer(self) -> None:
        if not self.boost_own_live_viewers:
            return
        match = re.search(r"(\d+)\s*$", self.name)
        if match:
            time.sleep(int(match.group(1)) * 3)
        proc = self.client.start_own_live_viewer(self.anchor_id)
        if proc is None:
            self._log(logging.WARNING, "Gagal jalankan browser viewer live sendiri")
            return
        self._own_live_viewer = proc
        self._log(
            logging.INFO,
            "Browser viewer live sendiri aktif (https://gosh.com/%s)",
            self.anchor_id,
        )

    def _stop_own_live_viewer(self) -> None:
        proc = self._own_live_viewer
        if proc is None:
            return
        self._own_live_viewer = None
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def run(self, stop_event: threading.Event) -> None:
        self.ensure_login()
        self.log_startup()
        self._start_own_live_viewer()

        try:
            if self.comment_feed is not None:
                while not stop_event.is_set():
                    try:
                        parsed = self.comment_feed.wait_for_comment(
                            self.name,
                            stop_event,
                        )
                        if parsed is None:
                            continue
                        self._handle_comment(parsed, stop_event)
                    except Exception as exc:
                        self._log(logging.ERROR, "Error: %s", exc)
                return

            while not stop_event.is_set():
                try:
                    data = self.client.fetch_messages(self.anchor_id)
                    msgs = data.get("msgs") or []
                    if self.verbose and not msgs:
                        self._log(logging.INFO, "Polling... belum ada komen baru")

                    for raw_msg in msgs:
                        if stop_event.is_set():
                            break

                        parsed = parse_chat_message(raw_msg)
                        if not parsed:
                            if self.verbose:
                                self._log(
                                    logging.INFO,
                                    "Lewati pesan non-komentar seq=%s",
                                    raw_msg.get("sequence"),
                                )
                            continue

                        parsed["_sequence"] = raw_msg.get("sequence")
                        self._handle_comment(parsed, stop_event)

                    wait_ms = int(data.get("next_internal_millis") or 0)
                    poll_ms = int(self.poll_interval * 1000) if self.poll_interval > 0 else 0
                    floor_ms = int(self.min_poll_interval * 1000)
                    sleep_ms = max(wait_ms, poll_ms, floor_ms)
                    if sleep_ms > 0 and not stop_event.is_set():
                        stop_event.wait(sleep_ms / 1000)

                except Exception as exc:
                    self._log(logging.ERROR, "Error: %s", exc)
                    if self.poll_interval > 0:
                        stop_event.wait(self.poll_interval)
        finally:
            self._stop_own_live_viewer()


def run_comment_poller(
    account: dict,
    feed: SharedCommentFeed,
    stop_event: threading.Event,
) -> None:
    """Poll fetch_msg sekali, broadcast ke semua akun bot."""
    name = account["name"]
    anchor_id = account["anchor_id"]
    poll_interval = float(account.get("poll_interval_seconds") or 0)
    min_poll_interval = float(account.get("min_poll_interval_seconds") or 0)
    verbose = bool(account.get("verbose_polling"))

    client = GoshClient(
        cookies_file=account["cookies_file"] if account.get("use_saved_session") else None,
        load_cookies=bool(account.get("use_saved_session")),
        proxy=account.get("proxy"),
    )
    login_cfg = account["login"]
    if not client.uid:
        log.info("[%s-poller] Login untuk polling komentar...", name)
        client.login(
            login_cfg["email"],
            login_cfg["password"],
            sm_box_id=account["sm_box_id"],
        )
        client.save_cookies(account["cookies_file"])
    log.info("[%s-poller] Polling komentar https://gosh.com/%s (shared)", name, anchor_id)

    while not stop_event.is_set():
        try:
            data = client.fetch_messages(anchor_id)
            msgs = data.get("msgs") or []
            if verbose and not msgs:
                log.info("[%s-poller] Belum ada komen baru", name)

            for raw_msg in msgs:
                if stop_event.is_set():
                    break
                parsed = parse_chat_message(raw_msg)
                if not parsed:
                    continue
                if feed.push(parsed, raw_msg.get("sequence")) and verbose:
                    log.info(
                        "[%s-poller] Komentar baru seq=%s dari %s",
                        name,
                        raw_msg.get("sequence"),
                        parsed["nickname"],
                    )

            wait_ms = int(data.get("next_internal_millis") or 0)
            poll_ms = int(poll_interval * 1000) if poll_interval > 0 else 0
            floor_ms = int(min_poll_interval * 1000)
            sleep_ms = max(wait_ms, poll_ms, floor_ms)
            if sleep_ms > 0 and not stop_event.is_set():
                stop_event.wait(sleep_ms / 1000)
        except Exception as exc:
            log.error("[%s-poller] Error: %s", name, exc)
            if poll_interval > 0:
                stop_event.wait(poll_interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gosh Live bot absen otomatis")
    parser.add_argument("-c", "--config", default="config.json", help="Path config JSON")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        accounts = resolve_accounts(config)
    except (FileNotFoundError, ValueError) as exc:
        log.error("%s", exc)
        return 1

    log.info("Menjalankan %d akun bot", len(accounts))
    account_names = [account["name"] for account in accounts]
    stagger = ReplyStaggerCoordinator(
        account_names,
        min_seconds=float(config.get("reply_stagger_min_seconds", 5)),
        max_seconds=float(config.get("reply_stagger_max_seconds", 15)),
    )
    default_min_poll = 2.0 if len(accounts) > 1 else 0.0
    min_poll = float(config.get("min_poll_interval_seconds", default_min_poll))
    for account in accounts:
        account.setdefault("min_poll_interval_seconds", min_poll)

    use_shared_poller = len(accounts) > 1
    comment_feed: SharedCommentFeed | None = None
    fleet_registry = FleetRegistry()
    if use_shared_poller:
        comment_feed = SharedCommentFeed(account_names)
        log.info(
            "Polling komentar terpusat (akun %s) — semua bot dapat komen yang sama",
            accounts[0]["name"],
        )

    if stagger.enabled:
        log.info(
            "Jeda antar akun (follow + absen): %.0f-%.0fs (acak)",
            stagger.min_seconds,
            stagger.max_seconds,
        )
    if min_poll > 0:
        log.info("Polling minimum: %.1fs", min_poll)
    log.info("Tekan Ctrl+C untuk berhenti.")

    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    if use_shared_poller and comment_feed is not None:
        poller_thread = threading.Thread(
            target=run_comment_poller,
            args=(accounts[0], comment_feed, stop_event),
            name="gosh-bot-poller",
            daemon=True,
        )
        poller_thread.start()
        threads.append(poller_thread)

    for account in accounts:
        bot = AccountBot(
            account,
            comment_feed=comment_feed,
            reply_stagger=stagger,
            fleet_registry=fleet_registry,
        )
        thread = threading.Thread(
            target=bot.run,
            args=(stop_event,),
            name=f"gosh-bot-{account['name']}",
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    try:
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.2)
    except KeyboardInterrupt:
        log.info("Menghentikan semua akun...")
        stop_event.set()
        for thread in threads:
            thread.join(timeout=5)
        log.info("Bot dihentikan.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
