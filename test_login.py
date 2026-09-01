#!/usr/bin/env python3
"""Tes login email/password tanpa menjalankan bot."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gosh_client import GoshClient


def main() -> int:
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "config.json")
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    login = cfg.get("login") or {}
    email = login.get("email", "").strip()
    password = login.get("password", "").strip()
    sm_box_id = (cfg.get("sm_box_id") or login.get("sm_box_id") or "").strip()

    if not email or not password:
        print("Isi login.email dan login.password di config.json")
        return 1
    if not sm_box_id:
        print("sm_box_id kosong. Jalankan: python3 get_sm_box_id.py")
        return 1

    client = GoshClient(load_cookies=False)
    try:
        client.login(email, password, sm_box_id=sm_box_id)
    except RuntimeError as exc:
        print(f"GAGAL: {exc}")
        return 1

    cookies_file = cfg.get("cookies_file", "cookies.json")
    client.save_cookies(cookies_file)
    print(f"OK — login berhasil (uid={client.uid})")
    print(f"Sesi disimpan ke {cookies_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
