#!/usr/bin/env python3
"""Ambil sm_box_id dari browser untuk login email Gosh."""

print(
    """
Cara ambil sm_box_id (sekali saja, copy ke config.json):

1. Buka https://gosh.com di Chrome/Edge (jangan incognito)
2. Tekan F12 → tab Console
3. Paste perintah ini lalu Enter:

   localStorage.getItem('pc__sm_box_id')

4. Copy hasilnya (string panjang diawali "DeyJ...")
5. Tempel ke config.json:

   "sm_box_id": "PASTE_DISINI"

Catatan:
- sm_box_id terikat browser/perangkat, bukan akun
- Kalau login gagal lagi nanti, ulangi langkah di atas
"""
)
