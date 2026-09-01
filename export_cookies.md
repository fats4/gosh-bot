# Cara Export Cookies Gosh (jika login API gagal)

Error `Param error(1051)` biasanya berarti:

1. Email/password salah, **atau**
2. Akun didaftarkan lewat **Google/Apple**, bukan email/password

Jika kamu login Gosh lewat Google/Apple, bot **tidak bisa** pakai email/password.
Pakai cookies dari browser:

## Langkah

1. Buka https://gosh.com dan login manual
2. Tekan `F12` → tab **Application** → **Cookies** → `https://gosh.com`
3. Salin cookies penting ke `cookies.json`:

```json
{
  "cookies": [
    {"name": "uid", "value": "15887479", "domain": ".gosh.com", "path": "/"},
    {"name": "session_id", "value": "...", "domain": ".gosh.com", "path": "/"},
    {"name": "tim_user_sig", "value": "...", "domain": ".gosh.com", "path": "/"},
    {"name": "signin_type", "value": "2", "domain": ".gosh.com", "path": "/"},
    {"name": "did", "value": "...", "domain": ".gosh.com", "path": "/"},
    {"name": "smidV2", "value": "...", "domain": ".gosh.com", "path": "/"}
  ]
}
```

4. Jalankan bot lagi: `python3 bot.py`

Bot akan otomatis pakai cookies jika file `cookies.json` ada.
