#!/usr/bin/env python3
"""Gosh Bot — CLI all-in-one."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from bot import load_config, resolve_accounts, run_bot
from setup_config import (
    cmd_proxy_from_file,
    cmd_proxy_test,
    cmd_quick_setup,
    cmd_quick_update,
    cmd_set_sm_box,
    cmd_show,
    cmd_validate,
    register_config_commands,
    validate_config,
)
from test_login import run_login_tests

ROOT = Path(__file__).resolve().parent
BOT_PATTERNS = (
    "python3 bot.py",
    "python bot.py",
    "gosh.py run",
    f"{ROOT}/gosh.py run",
)


def cmd_run(args: argparse.Namespace) -> int:
    if args.daemon and not args.foreground:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "run",
            "-c",
            args.config,
            "--foreground",
        ]
        with log_path.open("a", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(f"Bot berjalan di background (PID {proc.pid})")
        print(f"Log: {log_path.resolve()}")
        return 0
    return run_bot(args.config)


def _find_bot_processes() -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return result
    for line in out.splitlines():
        if "python" not in line:
            continue
        if "bot.py" in line or ("gosh.py" in line and " run" in line):
            if "grep" in line:
                continue
            parts = line.split(None, 10)
            if len(parts) >= 2 and parts[1].isdigit():
                result.append((int(parts[1]), line))
    return result


def cmd_stop(_args: argparse.Namespace) -> int:
    procs = _find_bot_processes()
    if not procs:
        print("Bot tidak berjalan.")
        return 0

    pids = sorted({pid for pid, _ in procs})
    print(f"Menghentikan {len(pids)} proses bot...")
    for pid in pids:
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass

    subprocess.run(
        [
            "pkill",
            "-f",
            "browser_watch",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "pkill",
            "-f",
            "puppeteer/.local-chromium",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("Bot dihentikan.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    procs = _find_bot_processes()
    print("=== Status Bot ===")
    if procs:
        print(f"Bot: BERJALAN ({len(procs)} proses)")
        for pid, line in procs[:5]:
            print(f"  PID {pid}")
    else:
        print("Bot: STOP")

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config: tidak ditemukan ({config_path})")
        return 0 if not procs else 0

    try:
        cfg = load_config(str(config_path))
        accounts = resolve_accounts(cfg)
        errors = validate_config(cfg)
        print(f"Config: {config_path} — {len(accounts)} akun")
        if errors:
            print("Validasi: BELUM LENGKAP")
            for err in errors[:5]:
                print(f"  - {err}")
        else:
            print("Validasi: OK")
        with_proxy = sum(1 for acc in cfg.get("accounts") or [] if acc.get("proxy"))
        if with_proxy:
            print(f"Proxy: {with_proxy}/{len(accounts)} akun")
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Config error: {exc}")
        return 1
    return 0


def cmd_login_test(args: argparse.Namespace) -> int:
    return run_login_tests(args.config)


def cmd_sm_box(args: argparse.Namespace) -> int:
    if args.value:
        return cmd_set_sm_box(args)
    print(
        """
Cara ambil sm_box_id (sekali saja, copy ke config):

1. Buka https://gosh.com di Chrome/Edge (jangan incognito)
2. Tekan F12 → tab Console
3. Paste perintah ini lalu Enter:

   localStorage.getItem('pc__sm_box_id')

4. Copy hasilnya (string panjang diawali "DeyJ...")
5. Set via CLI:

   python3 gosh.py sm-box "PASTE_DISINI"
   python3 gosh.py config set-sm-box "PASTE_DISINI"
"""
    )
    return 0


def make_args(config: str = "config.json", **kwargs) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "config": config,
        "file": None,
        "username": None,
        "password": None,
        "reveal": False,
        "timeout": "20",
        "value": None,
        "force": False,
        "yes": False,
        "daemon": False,
        "foreground": False,
        "log": "bot.log",
        "allow_partial": False,
        "name": None,
        "email": None,
        "anchor_id": None,
        "proxy": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _pause() -> None:
    input("\nTekan Enter untuk kembali ke menu...")


def _menu_header(config: str) -> None:
    procs = _find_bot_processes()
    bot_state = f"BERJALAN ({len(procs)})" if procs else "STOP"
    print("\n" + "=" * 44)
    print("       GOSH LIVE BOT")
    print("=" * 44)
    print(f"  Config : {config}")
    print(f"  Bot    : {bot_state}")
    print("=" * 44)


def _run_config_submenu(config: str) -> None:
    while True:
        print("\n--- Setup Config ---")
        print("  1. Setup cepat (baru / ulang)")
        print("  2. Update config (sm_box / proxy / password)")
        print("  3. Sync proxy dari file txt")
        print("  4. Cek status config")
        print("  5. Lihat config")
        print("  0. Kembali")
        choice = input("\nPilih: ").strip()
        if choice == "0":
            return
        if choice == "1":
            cmd_quick_setup(make_args(config))
        elif choice == "2":
            cmd_quick_update(make_args(config))
        elif choice == "3":
            cmd_proxy_from_file(make_args(config))
        elif choice == "4":
            cmd_validate(make_args(config))
        elif choice == "5":
            cmd_show(make_args(config))
        else:
            print("Pilihan tidak valid.")
            continue
        _pause()


def interactive_menu(config: str = "config.json") -> int:
    """Menu interaktif saat program dijalankan tanpa argumen."""
    while True:
        _menu_header(config)
        print("\n  1. Jalankan bot (foreground)")
        print("  2. Jalankan bot (background)")
        print("  3. Hentikan bot")
        print("  4. Status bot & config")
        print("  5. Setup config")
        print("  6. Tes login semua akun")
        print("  7. Tes proxy")
        print("  0. Keluar")
        choice = input("\nPilih menu: ").strip()

        if choice == "0":
            print("Sampai jumpa.")
            return 0
        if choice == "1":
            print("\nBot berjalan. Tekan Ctrl+C untuk stop.\n")
            try:
                run_bot(config)
            except KeyboardInterrupt:
                print("\nBot dihentikan.")
            _pause()
        elif choice == "2":
            cmd_run(make_args(config, daemon=True, foreground=False, log="bot.log"))
            _pause()
        elif choice == "3":
            cmd_stop(make_args(config))
            _pause()
        elif choice == "4":
            cmd_status(make_args(config))
            _pause()
        elif choice == "5":
            _run_config_submenu(config)
        elif choice == "6":
            cmd_login_test(make_args(config))
            _pause()
        elif choice == "7":
            cmd_proxy_test(make_args(config, timeout="20"))
            _pause()
        else:
            print("Pilihan tidak valid.")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path config.json (default: config.json)",
    )

    parser = argparse.ArgumentParser(
        prog="gosh",
        description="Gosh Live Bot — CLI all-in-one",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh cepat:
  python3 gosh.py config wizard       # setup config interaktif
  python3 gosh.py config validate     # cek config
  python3 gosh.py login test          # tes login semua akun
  python3 gosh.py config proxy test   # tes proxy
  python3 gosh.py run                 # jalankan bot (foreground)
  python3 gosh.py run -d              # jalankan di background
  python3 gosh.py status              # cek status
  python3 gosh.py stop                # hentikan bot
        """,
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path config.json (default: config.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Jalankan bot", parents=[common])
    p_run.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        help="Jalankan di background (log ke bot.log)",
    )
    p_run.add_argument(
        "--foreground",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p_run.add_argument(
        "--log",
        default="bot.log",
        help="File log saat --daemon (default: bot.log)",
    )
    p_run.set_defaults(func=cmd_run)

    p_stop = sub.add_parser("stop", help="Hentikan bot yang sedang berjalan", parents=[common])
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="Status bot dan config", parents=[common])
    p_status.set_defaults(func=cmd_status)

    p_login = sub.add_parser("login", help="Tes login akun", parents=[common])
    login_sub = p_login.add_subparsers(dest="login_cmd", required=True)
    p_login_test = login_sub.add_parser("test", help="Tes login semua akun", parents=[common])
    p_login_test.set_defaults(func=cmd_login_test)

    p_sm = sub.add_parser("sm-box", help="Panduan / set sm_box_id", parents=[common])
    p_sm.add_argument("value", nargs="?", help="Nilai sm_box_id (opsional)")
    p_sm.set_defaults(func=cmd_sm_box)

    p_config = sub.add_parser("config", help="Kelola config.json", parents=[common])
    config_sub = p_config.add_subparsers(dest="config_cmd", required=True)
    register_config_commands(config_sub, parents=[common])

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        raise SystemExit(interactive_menu())
    raise SystemExit(main())
