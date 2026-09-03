#!/usr/bin/env python3
"""Tes login email/password tanpa menjalankan bot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bot import resolve_accounts
from gosh_client import GoshClient


def test_account(account: dict) -> bool:
    name = account["name"]
    login = account["login"]
    email = login["email"]
    password = login["password"]
    sm_box_id = account["sm_box_id"]
    cookies_file = account["cookies_file"]

    client = GoshClient(load_cookies=False)
    try:
        client.login(email, password, sm_box_id=sm_box_id)
    except RuntimeError as exc:
        print(f"[{name}] GAGAL: {exc}")
        return False

    client.save_cookies(cookies_file)
    print(f"[{name}] OK — login berhasil (uid={client.uid})")
    print(f"[{name}] Sesi disimpan ke {cookies_file}")
    return True


def run_login_tests(config_path: str = "config.json") -> int:
    path = Path(config_path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        accounts = resolve_accounts(cfg)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Config error: {exc}")
        return 1

    ok = 0
    for account in accounts:
        if test_account(account):
            ok += 1

    print(f"\nHasil: {ok}/{len(accounts)} akun berhasil login")
    return 0 if ok == len(accounts) else 1


def main() -> int:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    return run_login_tests(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
