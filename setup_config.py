#!/usr/bin/env python3
"""CLI interaktif untuk mengisi dan mengelola config.json."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

DEFAULT_CONFIG: dict[str, Any] = {
    "reply_from_name": "Faats [KNJ 05]",
    "randomize_reply": True,
    "reply_message": "absen kak, hadir dari Faats [KNJ 05]",
    "reply_messages": [
        "absen kak, hadir dari {from_name}",
        "wak hadir bang, absen dari {from_name}",
        "hadir kak, absen {from_name}",
        "absen kak, {from_name} hadir",
        "hadir bang, absen dari {from_name} ya",
    ],
    "poll_interval_seconds": 0,
    "cooldown_per_user_seconds": 0,
    "skip_bot_accounts": False,
    "skip_fleet_accounts": True,
    "auto_follow_on_comment": False,
    "auto_follow_anchor": False,
    "auto_reply_on_comment": True,
    "watch_before_comment_seconds": 15,
    "boost_own_live_viewers": True,
    "boost_viewer_use_proxy": False,
    "reply_stagger_min_seconds": 5,
    "reply_stagger_max_seconds": 15,
    "rate_limit_retry_min_seconds": 15,
    "rate_limit_retry_max_seconds": 30,
    "min_poll_interval_seconds": 2,
    "verbose_polling": False,
    "use_saved_session": False,
    "sm_box_id": "",
    "accounts": [],
}

# Warna nickname chat di live (hex). Tiap akun dapat warna berbeda jika tidak di-set manual.
DEFAULT_CHAT_NAME_COLORS = (
    "#FF6D1C",
    "#33DCFF",
    "#B160EB",
    "#49FD94",
    "#FF3A8E",
    "#F40B3F",
    "#00CE94",
    "#D91FFF",
)

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

GLOBAL_BOOL_KEYS = (
    "randomize_reply",
    "skip_bot_accounts",
    "skip_fleet_accounts",
    "auto_follow_on_comment",
    "auto_follow_anchor",
    "auto_reply_on_comment",
    "boost_own_live_viewers",
    "boost_viewer_use_proxy",
    "verbose_polling",
    "use_saved_session",
)

GLOBAL_INT_KEYS = (
    "poll_interval_seconds",
    "cooldown_per_user_seconds",
    "watch_before_comment_seconds",
    "reply_stagger_min_seconds",
    "reply_stagger_max_seconds",
    "rate_limit_retry_min_seconds",
    "rate_limit_retry_max_seconds",
    "min_poll_interval_seconds",
)


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(DEFAULT_CONFIG)
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(path: Path, cfg: dict[str, Any]) -> None:
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        print(f"Backup disimpan: {backup}")
    path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Config disimpan: {path}")


def mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return "(kosong)"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return value[:visible] + "..." + value[-visible:]


def prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value if value else default


def prompt_required(text: str, default: str = "") -> str:
    while True:
        value = prompt(text, default)
        if value:
            return value
        print("  Wajib diisi.")


def prompt_bool(text: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{text} ({hint}): ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1", "true")


def prompt_int(text: str, default: int) -> int:
    while True:
        raw = prompt(text, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  Masukkan angka bulat.")


def prompt_password(text: str = "Password", *, keep_existing: str = "") -> str:
    if keep_existing:
        use = prompt_bool("Gunakan password yang sudah ada?", True)
        if use:
            return keep_existing
    while True:
        value = getpass.getpass(f"{text}: ")
        if value:
            confirm = getpass.getpass("Konfirmasi password: ")
            if value == confirm:
                return value
            print("  Password tidak cocok, coba lagi.")
        else:
            print("  Password wajib diisi.")


def normalize_proxy(raw: str, user: str = "", password: str = "") -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if "@" in raw or raw.startswith(("http://", "https://", "socks5://")):
        return raw if "://" in raw else f"http://{raw}"
    host_port = raw.split("://")[-1]
    if user and password:
        return f"http://{user}:{password}@{host_port}"
    return f"http://{host_port}"


def read_proxy_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"File proxy tidak ditemukan: {path}")
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def sync_proxies_from_file(
    cfg: dict[str, Any],
    file_path: str | Path | None = None,
    *,
    proxy_user: str = "",
    proxy_pass: str = "",
    save_path: Path | None = None,
) -> tuple[int, int]:
    """Assign proxy dari file txt ke setiap akun (1 baris = 1 akun).

    Returns (jumlah_akun_terassign, jumlah_proxy_unik_di_file).
    """
    accounts = cfg.get("accounts") or []
    if not accounts:
        raise ValueError("Belum ada akun di config.")

    path = Path(
        file_path
        or cfg.get("proxy_list_file")
        or "proxies.txt"
    )
    user = proxy_user or str(cfg.get("proxy_username") or "")
    password = proxy_pass or str(cfg.get("proxy_password") or "")

    proxy_lines = read_proxy_file(path)
    if not proxy_lines:
        raise ValueError(f"Tidak ada proxy di file: {path}")

    assigned, total_unique = assign_proxies_to_accounts(accounts, proxy_lines, user, password)
    cfg["accounts"] = accounts
    cfg["proxy_list_file"] = str(path)

    if save_path is not None:
        save_config(save_path, cfg)

    return assigned, total_unique


def load_proxy_pool(cfg: dict[str, Any]) -> list[str]:
    """Muat semua proxy unik dari file (pool untuk rotasi jika proxy mati)."""
    path = Path(cfg.get("proxy_list_file") or "proxies.txt")
    if not path.exists():
        return []
    user = str(cfg.get("proxy_username") or "")
    password = str(cfg.get("proxy_password") or "")
    lines = unique_proxy_lines(read_proxy_file(path))
    return [normalize_proxy(line, user, password) for line in lines]


def cmd_proxy_from_file(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    file_path = args.file or cfg.get("proxy_list_file") or "proxies.txt"

    if args.username:
        cfg["proxy_username"] = args.username
    if args.password:
        cfg["proxy_password"] = args.password
    if not cfg.get("proxy_username") and not args.username:
        user = prompt("Username proxy ProxyScrape", "")
        if user:
            cfg["proxy_username"] = user
            cfg["proxy_password"] = getpass.getpass("Password proxy: ")

    try:
        assigned, total = sync_proxies_from_file(
            cfg,
            file_path,
            save_path=path,
        )
    except (FileNotFoundError, ValueError) as exc:
        eprint(exc)
        return 1

    account_count = len(cfg.get("accounts") or [])
    print(f"File: {total} proxy unik | Akun: {account_count}")
    print(f"Assign: asisten1 ← baris 1, asisten2 ← baris 2, ... ({assigned} akun)")
    if assigned < account_count:
        print("Peringatan: proxy di file tidak cukup untuk semua akun.")
    elif total > account_count:
        print(f"Sisa {total - assigned} proxy di file tidak dipakai (normal jika file 100 proxy).")
    return 0


def parse_proxy_list(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def find_account(cfg: dict[str, Any], name: str) -> dict[str, Any] | None:
    for acc in cfg.get("accounts") or []:
        if acc.get("name") == name:
            return acc
    return None


def normalize_chat_color(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if HEX_COLOR_RE.match(raw):
        return raw.upper()
    return None


def default_chat_color_for_index(index: int) -> str:
    return DEFAULT_CHAT_NAME_COLORS[index % len(DEFAULT_CHAT_NAME_COLORS)]


def assign_chat_colors(
    accounts: list[dict[str, Any]],
    *,
    overwrite: bool = False,
) -> int:
    """Assign chat_name_color ke tiap akun. Return jumlah akun yang diubah."""
    changed = 0
    for index, acc in enumerate(accounts):
        if not overwrite and str(acc.get("chat_name_color") or "").strip():
            continue
        acc["chat_name_color"] = default_chat_color_for_index(index)
        changed += 1
    return changed


def print_chat_colors(accounts: list[dict[str, Any]], *, resolved: bool = False) -> None:
    if not accounts:
        print("Belum ada akun.")
        return
    print("\nWarna nickname chat:")
    for index, acc in enumerate(accounts):
        name = str(acc.get("name") or f"acc{index + 1}")
        color = str(acc.get("chat_name_color") or "").strip()
        if not color and resolved:
            color = default_chat_color_for_index(index)
            note = " (auto saat bot jalan)"
        elif not color:
            color = default_chat_color_for_index(index)
            note = " (belum disimpan — auto saat bot jalan)"
        else:
            note = ""
        print(f"  {name}: {color}{note}")
    print("\nPalet default:", ", ".join(DEFAULT_CHAT_NAME_COLORS))


def validate_config(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(cfg.get("sm_box_id") or "").strip():
        errors.append("sm_box_id belum diisi (global).")
    accounts = cfg.get("accounts") or []
    if not accounts:
        errors.append("Belum ada akun di accounts[].")
    names: set[str] = set()
    for index, acc in enumerate(accounts, start=1):
        name = str(acc.get("name") or f"acc{index}").strip()
        if not name:
            errors.append(f"Akun #{index}: name kosong.")
            continue
        if name in names:
            errors.append(f"Akun '{name}': nama duplikat.")
        names.add(name)
        if not str(acc.get("anchor_id") or "").strip():
            errors.append(f"Akun '{name}': anchor_id wajib.")
        login = acc.get("login") or {}
        if not str(login.get("email") or "").strip():
            errors.append(f"Akun '{name}': login.email wajib.")
        if not str(login.get("password") or "").strip():
            errors.append(f"Akun '{name}': login.password wajib.")
        color = str(acc.get("chat_name_color") or "").strip()
        if color and not normalize_chat_color(color):
            errors.append(f"Akun '{name}': chat_name_color tidak valid (pakai hex, mis. #FF6D1C).")
    return errors


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.exists() and not args.force:
        eprint(f"{path} sudah ada. Pakai --force untuk timpa, atau perintah wizard/edit.")
        return 1
    cfg = deepcopy(DEFAULT_CONFIG)
    save_config(path, cfg)
    print("Config kosong dibuat. Lanjutkan dengan: python3 setup_config.py wizard")
    return 0


def prompt_password_simple(text: str = "Password", *, default: str = "") -> str:
    if default:
        use = prompt_bool(f"Pakai {text} yang sudah ada?", True)
        if use:
            return default
    while True:
        value = getpass.getpass(f"{text}: ")
        if value:
            return value
        print("  Wajib diisi.")


def prompt_multiline(title: str) -> list[str]:
    print(title)
    print("(Tempel daftar, lalu Enter di baris kosong)")
    lines: list[str] = []
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line.strip())
    return lines


def unique_proxy_lines(proxy_lines: list[str]) -> list[str]:
    """Buang duplikat host:port, urutan file tetap."""
    seen: set[str] = set()
    unique: list[str] = []
    for line in proxy_lines:
        key = line.strip().split("@")[-1].split("://")[-1].lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(line.strip())
    return unique


def assign_proxies_to_accounts(
    accounts: list[dict[str, Any]],
    proxy_lines: list[str],
    proxy_user: str = "",
    proxy_pass: str = "",
) -> tuple[int, int]:
    """Return (assigned_count, total_unique_in_file)."""
    unique_lines = unique_proxy_lines(proxy_lines)
    proxies = [normalize_proxy(line, proxy_user, proxy_pass) for line in unique_lines]
    for index, acc in enumerate(accounts):
        if index < len(proxies):
            acc["proxy"] = proxies[index]
        else:
            acc.pop("proxy", None)
    return min(len(accounts), len(proxies)), len(unique_lines)


def build_accounts_from_emails(
    emails: list[str],
    *,
    anchor_id: str,
    password: str,
    prefix: str = "asisten",
) -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    for index, email in enumerate(emails, start=1):
        email = email.strip()
        if not email or "@" not in email:
            continue
        name = f"{prefix}{index}"
        accounts.append(
            {
                "name": name,
                "anchor_id": anchor_id,
                "login": {"email": email, "password": password},
                "cookies_file": f"cookies_bot{index}.json",
                "chat_name_color": default_chat_color_for_index(index - 1),
            }
        )
    return accounts


def print_sm_box_hint() -> None:
    print("  Cara ambil: gosh.com → F12 → Console → localStorage.getItem('pc__sm_box_id')")


def cmd_quick_setup(args: argparse.Namespace) -> int:
    """Setup config singkat: sm_box + anchor + tempel email + proxy."""
    path = Path(args.config)
    cfg = load_config(path)
    existing = bool(cfg.get("accounts")) or bool(str(cfg.get("sm_box_id") or "").strip())

    print("\n=== Setup Cepat ===\n")
    if existing:
        print("Config sudah ada.")
        mode = prompt("Mode: (1) setup ulang  (2) update saja", "2").strip()
    else:
        mode = "1"

    if mode == "2":
        return cmd_quick_update(args)

    # --- Setup ulang (4 langkah) ---
    print("\n[1/4] sm_box_id")
    print_sm_box_hint()
    cfg["sm_box_id"] = prompt_required("sm_box_id", str(cfg.get("sm_box_id") or ""))

    print("\n[2/4] Live anchor")
    anchor_id = prompt_required("Anchor ID", "15887479")
    reply_name = prompt("Nama pengirim absen", str(cfg.get("reply_from_name") or "Faats [KNJ 05]"))
    cfg["reply_from_name"] = reply_name

    print("\n[3/4] Akun bot")
    old_pass = ""
    if cfg.get("accounts"):
        old_pass = str((cfg["accounts"][0].get("login") or {}).get("password") or "")
    password = prompt_password_simple("Password login (sama untuk semua akun)", default=old_pass)

    emails = prompt_multiline("Tempel email (1 baris = 1 akun):")
    if not emails:
        print("Minimal 1 email diperlukan.")
        return 1
    accounts = build_accounts_from_emails(emails, anchor_id=anchor_id, password=password)

    print("\n[4/4] Proxy dari file txt (opsional)")
    if prompt_bool("Pakai proxy dari file txt?", True):
        file_path = prompt("Path file proxy", str(cfg.get("proxy_list_file") or "proxies.txt"))
        cfg["proxy_list_file"] = file_path
        cfg["proxy_username"] = prompt(
            "Username proxy ProxyScrape",
            str(cfg.get("proxy_username") or ""),
        )
        if cfg["proxy_username"]:
            cfg["proxy_password"] = getpass.getpass("Password proxy: ") or str(cfg.get("proxy_password") or "")
        cfg["accounts"] = accounts
        try:
            assigned, total = sync_proxies_from_file(cfg, file_path)
            print(f"Proxy: {assigned} akun dari {total} proxy di file.")
        except FileNotFoundError:
            print(f"\nFile belum ada: {file_path}")
            print("Upload file ProxyScrape ke folder gosh-bot, lalu jalankan:")
            print("  python3 gosh.py config proxy from-file")
            accounts = cfg["accounts"]

    cfg["accounts"] = accounts
    _print_setup_summary(cfg)
    if not prompt_bool("Simpan config?", True):
        print("Dibatalkan.")
        return 1

    save_config(path, cfg)
    print("\nSelesai! Jalankan: python3 gosh.py → pilih 1 (run bot)")
    return 0


def cmd_quick_update(args: argparse.Namespace) -> int:
    """Update sebagian config yang sudah ada."""
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []

    print("\nUpdate apa?\n")
    print("  1. sm_box_id")
    print("  2. Proxy semua akun")
    print("  3. Password semua akun")
    print("  4. Tambah akun (email baru)")
    print("  5. Warna chat akun")
    print("  0. Batal")
    choice = input("\nPilih: ").strip()

    if choice == "0":
        return 0
    if choice == "1":
        print_sm_box_hint()
        cfg["sm_box_id"] = prompt_required("sm_box_id", str(cfg.get("sm_box_id") or ""))
    elif choice == "2":
        if not accounts:
            print("Belum ada akun. Jalankan setup ulang dulu.")
            return 1
        file_path = prompt(
            "Path file proxy",
            str(cfg.get("proxy_list_file") or "proxies.txt"),
        )
        cfg["proxy_list_file"] = file_path
        if not cfg.get("proxy_username"):
            cfg["proxy_username"] = prompt("Username proxy ProxyScrape", "")
            if cfg["proxy_username"]:
                cfg["proxy_password"] = getpass.getpass("Password proxy: ")
        try:
            assigned, total = sync_proxies_from_file(cfg, file_path, save_path=path)
            print(f"Proxy: {assigned} akun dari {total} proxy di file.")
        except (FileNotFoundError, ValueError) as exc:
            print(f"Gagal: {exc}")
            return 1
    elif choice == "3":
        if not accounts:
            print("Belum ada akun.")
            return 1
        password = prompt_password_simple("Password baru")
        for acc in accounts:
            acc.setdefault("login", {})["password"] = password
    elif choice == "4":
        anchor_id = str(accounts[0].get("anchor_id") if accounts else prompt_required("Anchor ID", "15887479"))
        old_pass = str((accounts[0].get("login") or {}).get("password") or "") if accounts else ""
        password = prompt_password_simple("Password login", default=old_pass)
        start = len(accounts) + 1
        emails = prompt_multiline("Tempel email akun baru:")
        for index, email in enumerate(emails, start=start):
            email = email.strip()
            if not email or "@" not in email:
                continue
            name = f"asisten{index}"
            entry: dict[str, Any] = {
                "name": name,
                "anchor_id": anchor_id,
                "login": {"email": email, "password": password},
                "cookies_file": f"cookies_bot{index}.json",
                "chat_name_color": default_chat_color_for_index(index - 1),
            }
            accounts.append(entry)
        cfg["accounts"] = accounts
    elif choice == "5":
        if not accounts:
            print("Belum ada akun.")
            return 1
        return cmd_colors(args)
    else:
        print("Pilihan tidak valid.")
        return 1

    save_config(path, cfg)
    _print_setup_summary(cfg)
    return 0


def _print_setup_summary(cfg: dict[str, Any]) -> None:
    accounts = cfg.get("accounts") or []
    with_proxy = sum(1 for a in accounts if a.get("proxy"))
    print("\n--- Ringkasan ---")
    print(f"  Akun     : {len(accounts)}")
    if accounts:
        names = [str(a.get("name")) for a in accounts[:3]]
        extra = f" ... +{len(accounts) - 3}" if len(accounts) > 3 else ""
        print(f"             {', '.join(names)}{extra}")
    print(f"  Anchor   : {accounts[0].get('anchor_id') if accounts else '-'}")
    print(f"  Proxy    : {with_proxy}/{len(accounts)} akun")
    print(f"  sm_box   : {'OK' if cfg.get('sm_box_id') else 'BELUM'}")
    errors = validate_config(cfg)
    if errors:
        print("  Status   : BELUM LENGKAP")
        for err in errors[:3]:
            print(f"    - {err}")
    else:
        print("  Status   : OK")


def cmd_wizard(args: argparse.Namespace) -> int:
    """Alias setup cepat — wizard lama diganti flow singkat."""
    return cmd_quick_setup(args)


def cmd_show(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if not path.exists():
        eprint(f"Config tidak ditemukan: {path}")
        return 1
    cfg = load_config(path)
    display = deepcopy(cfg)
    if not args.reveal:
        if display.get("sm_box_id"):
            display["sm_box_id"] = mask_secret(str(display["sm_box_id"]), 8)
        for acc in display.get("accounts") or []:
            login = acc.get("login") or {}
            if login.get("password"):
                login["password"] = mask_secret(str(login["password"]))
            proxy = str(acc.get("proxy") or "")
            if proxy and "@" in proxy:
                acc["proxy"] = re.sub(
                    r"://([^:@/]+):([^@/]+)@", r"://\1:***@", proxy
                )
    print(json.dumps(display, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if not path.exists():
        eprint(f"Config tidak ditemukan: {path}")
        return 1
    cfg = load_config(path)
    errors = validate_config(cfg)
    if errors:
        print("Config BELUM valid:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"Config OK — {len(cfg.get('accounts') or [])} akun.")
    return 0


def cmd_global(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    print("\n=== Edit pengaturan global ===\n")
    cfg["reply_from_name"] = prompt("reply_from_name", str(cfg.get("reply_from_name") or ""))
    cfg["sm_box_id"] = prompt_required("sm_box_id", str(cfg.get("sm_box_id") or ""))
    for key in GLOBAL_BOOL_KEYS:
        cfg[key] = prompt_bool(key, bool(cfg.get(key, DEFAULT_CONFIG.get(key, False))))
    for key in GLOBAL_INT_KEYS:
        cfg[key] = prompt_int(key, int(cfg.get(key, DEFAULT_CONFIG.get(key, 0) or 0)))
    save_config(path, cfg)
    return 0


def cmd_account_add(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.setdefault("accounts", [])

    default_anchor = str(accounts[0].get("anchor_id") if accounts else "15887479")
    name = args.name or prompt_required("Nama akun")
    if find_account(cfg, name):
        eprint(f"Akun '{name}' sudah ada.")
        return 1

    email = args.email or prompt_required("Email login")
    password = args.password or prompt_password()
    anchor_id = args.anchor_id or prompt("anchor_id", default_anchor)
    proxy = args.proxy or prompt("Proxy (opsional)", "")

    entry: dict[str, Any] = {
        "name": name,
        "anchor_id": anchor_id,
        "login": {"email": email, "password": password},
        "cookies_file": f"cookies_{name}.json",
    }
    if proxy:
        entry["proxy"] = proxy
    entry["chat_name_color"] = default_chat_color_for_index(len(accounts))
    accounts.append(entry)
    save_config(path, cfg)
    return 0


def cmd_account_edit(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    acc = find_account(cfg, args.name)
    if not acc:
        eprint(f"Akun '{args.name}' tidak ditemukan.")
        return 1

    login = acc.setdefault("login", {})
    print(f"\nEdit akun '{args.name}' (Enter = keep)\n")
    accounts = cfg.get("accounts") or []
    acc_index = next(
        (index for index, item in enumerate(accounts) if item.get("name") == args.name),
        0,
    )
    new_name = prompt("name", str(acc.get("name") or ""))
    if new_name != args.name and find_account(cfg, new_name):
        eprint(f"Nama '{new_name}' sudah dipakai.")
        return 1
    acc["name"] = new_name
    acc["anchor_id"] = prompt("anchor_id", str(acc.get("anchor_id") or ""))
    login["email"] = prompt("email", str(login.get("email") or ""))
    if prompt_bool("Ubah password?", False):
        login["password"] = prompt_password()
    proxy = prompt("proxy", str(acc.get("proxy") or ""))
    if proxy:
        acc["proxy"] = proxy
    elif "proxy" in acc:
        del acc["proxy"]
    default_color = str(
        acc.get("chat_name_color") or default_chat_color_for_index(acc_index)
    )
    color = prompt("chat_name_color (hex)", default_color)
    normalized = normalize_chat_color(color)
    if normalized:
        acc["chat_name_color"] = normalized
    elif color.strip():
        eprint(f"Warna tidak valid: {color!r}. Gunakan format #RRGGBB.")
        return 1
    acc["cookies_file"] = str(acc.get("cookies_file") or f"cookies_{new_name}.json")
    save_config(path, cfg)
    return 0


def cmd_account_remove(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    new_accounts = [a for a in accounts if a.get("name") != args.name]
    if len(new_accounts) == len(accounts):
        eprint(f"Akun '{args.name}' tidak ditemukan.")
        return 1
    if not args.yes and not prompt_bool(f"Hapus akun '{args.name}'?", False):
        print("Dibatalkan.")
        return 1
    cfg["accounts"] = new_accounts
    save_config(path, cfg)
    return 0


def cmd_account_list(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    if not accounts:
        print("Belum ada akun.")
        return 0
    for acc in accounts:
        login = acc.get("login") or {}
        proxy = acc.get("proxy") or "-"
        if not args.reveal and proxy != "-" and "@" in str(proxy):
            proxy = re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:***@", str(proxy))
        print(
            f"- {acc.get('name')}: {login.get('email')} | anchor={acc.get('anchor_id')} "
            f"| warna={acc.get('chat_name_color') or '-'} | proxy={proxy}"
        )
    return 0


def cmd_proxy_import(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    if not accounts:
        eprint("Belum ada akun. Tambah dulu dengan wizard atau account add.")
        return 1

    if args.file:
        proxy_text = Path(args.file).read_text(encoding="utf-8")
    else:
        print("Tempel daftar proxy (baris kosong = selesai):")
        lines: list[str] = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        proxy_text = "\n".join(lines)

    proxy_user = args.user or prompt("Username proxy (kosong jika sudah ada di URL)", "")
    proxy_pass = args.password or ""
    if proxy_user and not proxy_pass:
        proxy_pass = getpass.getpass("Password proxy: ")

    proxies = [
        normalize_proxy(line, proxy_user, proxy_pass)
        for line in parse_proxy_list(proxy_text)
    ]
    if not proxies:
        eprint("Tidak ada proxy valid.")
        return 1

    for index, acc in enumerate(accounts):
        if index < len(proxies):
            acc["proxy"] = proxies[index]
        elif not args.allow_partial:
            acc.pop("proxy", None)

    save_config(path, cfg)
    print(f"Proxy diassign: {min(len(accounts), len(proxies))}/{len(accounts)} akun.")
    if len(proxies) < len(accounts):
        print(f"Peringatan: proxy hanya {len(proxies)}, akun sisanya tanpa proxy.")
    return 0


def cmd_proxy_test(args: argparse.Namespace) -> int:
    if requests is None:
        eprint("Modul requests belum terpasang.")
        return 1
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    if not accounts:
        eprint("Belum ada akun.")
        return 1

    ok = 0
    seen: dict[str, str] = {}
    for acc in accounts:
        name = acc.get("name", "?")
        proxy = str(acc.get("proxy") or "").strip()
        if not proxy:
            print(f"{name}: (tanpa proxy)")
            continue
        try:
            resp = requests.get(
                "https://api.ipify.org?format=json",
                proxies={"http": proxy, "https": proxy},
                timeout=int(args.timeout),
            )
            ip = resp.json().get("ip", "?")
            dup = seen.get(ip)
            seen[ip] = name
            note = f" DUPLIKAT dengan {dup}" if dup else ""
            print(f"{name}: OK -> {ip}{note}")
            ok += 1
        except Exception as exc:
            print(f"{name}: GAGAL -> {type(exc).__name__}")

    with_proxy = sum(1 for a in accounts if a.get("proxy"))
    print(f"\nBerhasil: {ok}/{with_proxy} proxy, IP unik: {len(seen)}")
    return 0 if ok == with_proxy else 1


def cmd_colors_list(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    print_chat_colors(accounts)
    return 0


def cmd_colors_auto(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    if not accounts:
        eprint("Belum ada akun.")
        return 1
    overwrite = bool(getattr(args, "overwrite", False))
    if overwrite and not getattr(args, "yes", False):
        if not prompt_bool("Timpa semua warna yang sudah ada?", False):
            print("Dibatalkan.")
            return 1
    changed = assign_chat_colors(accounts, overwrite=overwrite)
    save_config(path, cfg)
    print(f"Warna diassign ke {changed} akun.")
    print_chat_colors(accounts)
    return 0


def cmd_colors_set(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    acc = find_account(cfg, args.name)
    if not acc:
        eprint(f"Akun '{args.name}' tidak ditemukan.")
        return 1

    color_raw = args.color or prompt_required(
        f"Warna hex untuk {args.name}",
        str(acc.get("chat_name_color") or ""),
    )
    color = normalize_chat_color(color_raw)
    if not color:
        eprint(f"Warna tidak valid: {color_raw!r}. Gunakan format #RRGGBB.")
        return 1
    acc["chat_name_color"] = color
    save_config(path, cfg)
    print(f"{args.name} → {color}")
    return 0


def cmd_colors_edit(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    accounts = cfg.get("accounts") or []
    if not accounts:
        eprint("Belum ada akun.")
        return 1

    print("\n=== Edit warna per akun ===\n")
    print("Palet:", ", ".join(DEFAULT_CHAT_NAME_COLORS))
    print("Enter = lewati akun, kosongkan = pakai warna default urutan\n")
    for index, acc in enumerate(accounts):
        name = str(acc.get("name") or f"acc{index + 1}")
        current = str(acc.get("chat_name_color") or default_chat_color_for_index(index))
        value = prompt(f"{name}", current)
        if not value.strip():
            continue
        color = normalize_chat_color(value)
        if not color:
            eprint(f"Warna tidak valid: {value!r}. Lewati {name}.")
            continue
        acc["chat_name_color"] = color
    save_config(path, cfg)
    print("\nDisimpan.")
    print_chat_colors(accounts)
    return 0


def cmd_colors(args: argparse.Namespace) -> int:
    """Menu interaktif kelola warna chat."""
    path = Path(args.config)
    while True:
        cfg = load_config(path)
        accounts = cfg.get("accounts") or []
        print("\n=== Warna Chat Akun ===")
        print("  1. Lihat warna saat ini")
        print("  2. Auto-assign warna berbeda (akun tanpa warna saja)")
        print("  3. Auto-assign ulang semua akun")
        print("  4. Edit warna per akun")
        print("  5. Set warna 1 akun")
        print("  0. Kembali")
        choice = input("\nPilih: ").strip()
        if choice == "0":
            return 0
        if choice == "1":
            print_chat_colors(accounts)
        elif choice == "2":
            changed = assign_chat_colors(accounts, overwrite=False)
            save_config(path, cfg)
            print(f"Warna diassign ke {changed} akun.")
            print_chat_colors(accounts)
        elif choice == "3":
            if prompt_bool("Timpa semua warna yang sudah ada?", False):
                changed = assign_chat_colors(accounts, overwrite=True)
                save_config(path, cfg)
                print(f"Warna diassign ulang ke {changed} akun.")
                print_chat_colors(accounts)
            else:
                print("Dibatalkan.")
        elif choice == "4":
            cmd_colors_edit(args)
        elif choice == "5":
            if not accounts:
                print("Belum ada akun.")
                continue
            names = [str(a.get("name")) for a in accounts]
            print("Akun:", ", ".join(names))
            name = prompt_required("Nama akun", names[0])
            set_args = argparse.Namespace(config=args.config, name=name, color=None)
            cmd_colors_set(set_args)
        else:
            print("Pilihan tidak valid.")
        input("\nTekan Enter...")


def cmd_set_sm_box(args: argparse.Namespace) -> int:
    path = Path(args.config)
    cfg = load_config(path)
    value = args.value or prompt_required("sm_box_id", str(cfg.get("sm_box_id") or ""))
    cfg["sm_box_id"] = value
    save_config(path, cfg)
    return 0


def register_config_commands(
    sub: argparse._SubParsersAction,
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> None:
    """Daftarkan subcommand config ke parser induk."""
    parents = parents or []

    p_init = sub.add_parser("init", help="Buat config.json kosong", parents=parents)
    p_init.add_argument("--force", action="store_true", help="Timpa config yang sudah ada")
    p_init.set_defaults(func=cmd_init)

    p_wizard = sub.add_parser("wizard", help="Setup cepat config", parents=parents)
    p_wizard.set_defaults(func=cmd_wizard)

    p_quick = sub.add_parser("quick", help="Setup cepat (sama dengan wizard)", parents=parents)
    p_quick.set_defaults(func=cmd_quick_setup)

    p_update = sub.add_parser("update", help="Update sebagian config", parents=parents)
    p_update.set_defaults(func=cmd_quick_update)

    p_show = sub.add_parser("show", help="Tampilkan config (password di-mask)", parents=parents)
    p_show.add_argument("--reveal", action="store_true", help="Tampilkan secret tanpa mask")
    p_show.set_defaults(func=cmd_show)

    p_validate = sub.add_parser("validate", help="Validasi config.json", parents=parents)
    p_validate.set_defaults(func=cmd_validate)

    p_global = sub.add_parser("global", help="Edit pengaturan global", parents=parents)
    p_global.set_defaults(func=cmd_global)

    p_sm = sub.add_parser("set-sm-box", help="Set sm_box_id global", parents=parents)
    p_sm.add_argument("value", nargs="?", help="Nilai sm_box_id")
    p_sm.set_defaults(func=cmd_set_sm_box)

    p_colors = sub.add_parser(
        "colors",
        help="Kelola warna nickname chat per akun",
        parents=parents,
    )
    colors_sub = p_colors.add_subparsers(dest="colors_cmd")

    p_colors.set_defaults(func=cmd_colors, colors_cmd=None)

    p_colors_list = colors_sub.add_parser("list", help="Lihat warna tiap akun", parents=parents)
    p_colors_list.set_defaults(func=cmd_colors_list, colors_cmd="list")

    p_colors_auto = colors_sub.add_parser(
        "auto",
        help="Assign warna default ke akun",
        parents=parents,
    )
    p_colors_auto.add_argument(
        "--overwrite",
        action="store_true",
        help="Timpa warna yang sudah ada",
    )
    p_colors_auto.add_argument("-y", "--yes", action="store_true", help="Tanpa konfirmasi")
    p_colors_auto.set_defaults(func=cmd_colors_auto, colors_cmd="auto")

    p_colors_edit = colors_sub.add_parser(
        "edit",
        help="Edit warna semua akun (interaktif)",
        parents=parents,
    )
    p_colors_edit.set_defaults(func=cmd_colors_edit, colors_cmd="edit")

    p_colors_set = colors_sub.add_parser("set", help="Set warna 1 akun", parents=parents)
    p_colors_set.add_argument("name", help="Nama akun")
    p_colors_set.add_argument("color", nargs="?", help="Hex warna, mis. #FF6D1C")
    p_colors_set.set_defaults(func=cmd_colors_set, colors_cmd="set")

    p_acc = sub.add_parser("account", help="Kelola akun", parents=parents)
    acc_sub = p_acc.add_subparsers(dest="account_cmd", required=True)

    p_add = acc_sub.add_parser("add", help="Tambah akun", parents=parents)
    p_add.add_argument("--name")
    p_add.add_argument("--email")
    p_add.add_argument("--password")
    p_add.add_argument("--anchor-id")
    p_add.add_argument("--proxy")
    p_add.set_defaults(func=cmd_account_add)

    p_edit = acc_sub.add_parser("edit", help="Edit akun", parents=parents)
    p_edit.add_argument("name")
    p_edit.set_defaults(func=cmd_account_edit)

    p_rm = acc_sub.add_parser("remove", help="Hapus akun", parents=parents)
    p_rm.add_argument("name")
    p_rm.add_argument("-y", "--yes", action="store_true")
    p_rm.set_defaults(func=cmd_account_remove)

    p_list = acc_sub.add_parser("list", help="Daftar akun", parents=parents)
    p_list.add_argument("--reveal", action="store_true")
    p_list.set_defaults(func=cmd_account_list)

    p_proxy = sub.add_parser("proxy", help="Kelola proxy", parents=parents)
    proxy_sub = p_proxy.add_subparsers(dest="proxy_cmd", required=True)

    p_import = proxy_sub.add_parser("import", help="Import daftar proxy ke akun", parents=parents)
    p_import.add_argument("-f", "--file", help="File teks (satu proxy per baris)")
    p_import.add_argument("--user", help="Username proxy shared")
    p_import.add_argument("--password", help="Password proxy shared")
    p_import.add_argument(
        "--allow-partial",
        action="store_true",
        help="Biarkan akun tanpa proxy jika daftar proxy lebih sedikit",
    )
    p_import.set_defaults(func=cmd_proxy_import)

    p_from_file = proxy_sub.add_parser(
        "from-file",
        help="Assign proxy dari file txt (1 baris = 1 akun)",
        parents=parents,
    )
    p_from_file.add_argument(
        "-f",
        "--file",
        help="File proxy (default: proxies.txt / proxy_list_file di config)",
    )
    p_from_file.add_argument("--username", help="Username proxy ProxyScrape")
    p_from_file.add_argument("--password", help="Password proxy ProxyScrape")
    p_from_file.set_defaults(func=cmd_proxy_from_file)

    p_test = proxy_sub.add_parser("test", help="Tes koneksi proxy semua akun", parents=parents)
    p_test.add_argument("--timeout", default="20")
    p_test.set_defaults(func=cmd_proxy_test)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI untuk mengisi config.json Gosh Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python3 setup_config.py wizard
  python3 setup_config.py account add --name asisten1 --email a@b.com
  python3 setup_config.py proxy import --file proxies.txt
  python3 setup_config.py proxy test
  python3 setup_config.py show
        """,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path config.json (default: config.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)
    register_config_commands(sub)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "account" and not hasattr(args, "func"):
        parser.parse_args(["account", "-h"])
        return 1
    if args.command == "proxy" and not hasattr(args, "func"):
        parser.parse_args(["proxy", "-h"])
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
