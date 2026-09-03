# Gosh Live Bot — Absen Otomatis

Bot Python untuk [Gosh Live](https://gosh.com) yang memantau komentar di channel live kamu, lalu otomatis membalas **"absen kak, hadir"** di **live penonton yang komen**.

Contoh: seseorang komen di live kamu → bot masuk ke live mereka → kirim `"absen kak, hadir"`.

---

## Fitur

- Pantau komentar baru di channel kamu (online/offline)
- Deteksi komentar teks **dan emoji custom Gosh** (`[emoji:id]`)
- **Multi akun** — banyak bot dalam 1 config, 1 command
- **Auto-follow** penonton yang komen (bisa dimatikan)
- Balas otomatis di live penonton yang komen
- Cooldown per user (anti-spam)
- Login email/password via API Gosh
- Kirim chat lewat Tencent IM SDK (sama seperti website Gosh)

---

## Persyaratan

| Software | Versi minimum | Fungsi |
|----------|---------------|--------|
| **Python** | 3.10+ | Bot utama |
| **Node.js** | 12+ | Kirim chat (`tim_send.js`) |
| **npm** | 8+ | Install `@tencentcloud/chat` |
| **Akun Gosh** | — | Email + password |

---

## Instalasi

### 1. Clone repo

```bash
git clone https://github.com/USERNAME/gosh-bot.git
cd gosh-bot
```

### 2. Install dependency

```bash
pip install -r requirements.txt
npm install
```

### 3. Buat config

```bash
cp config.example.json config.json
```

Edit `config.json`. Bot mendukung **multi akun** dalam 1 file config.

### Format multi akun (disarankan)

```json
{
  "reply_message": "absen kak, hadir",
  "poll_interval_seconds": 0,
  "cooldown_per_user_seconds": 0,
  "sm_box_id": "DeyJ...",
  "accounts": [
    {
      "name": "bot1",
      "anchor_id": "15887479",
      "login": {
        "email": "akun1@gmail.com",
        "password": "password1"
      },
      "cookies_file": "cookies_bot1.json"
    },
    {
      "name": "bot2",
      "anchor_id": "15887479",
      "login": {
        "email": "akun2@gmail.com",
        "password": "password2"
      },
      "cookies_file": "cookies_bot2.json"
    }
  ]
}
```

Jalankan semua akun sekaligus:

```bash
python3 bot.py
```

Log tiap akun diberi prefix `[bot1]`, `[bot2]`, dst.

| Field | Wajib | Keterangan |
|-------|-------|------------|
| `accounts` | ✅ | Array akun bot |
| `accounts[].name` | — | Nama akun (untuk log). Default: `acc1`, `acc2`, ... |
| `accounts[].anchor_id` | ✅ | ID channel yang dipantau |
| `accounts[].login.email` | ✅ | Email akun Gosh |
| `accounts[].login.password` | ✅ | Password akun Gosh |
| `accounts[].cookies_file` | — | File sesi per akun. Default: `cookies_{name}.json` |
| `accounts[].enabled` | — | `false` untuk nonaktifkan akun tanpa hapus dari config |
| `sm_box_id` | ✅ | Token browser (bisa global, atau override per akun) |
| `reply_message` | — | Pesan tetap jika `randomize_reply: false` |
| `reply_from_name` | — | Nama yang di-absenkan. Default: `"Faats [KNJ 05]"` |
| `randomize_reply` | — | Acak variasi pesan absen. Default: `true` |
| `reply_messages` | — | Daftar template custom. Pakai `{from_name}` sebagai placeholder |
| `poll_interval_seconds` | — | Interval polling (detik). Default: `0` (tanpa delay) |
| `cooldown_per_user_seconds` | — | Jeda balasan ke user yang sama. Default: `0` |
| `skip_bot_accounts` | — | Lewati akun `bot_type: 1`. Default: `false` |
| `auto_follow_on_comment` | — | Follow otomatis penonton yang komen. Default: `true` |
| `watch_before_comment_seconds` | — | Durasi nonton live (detik) sebelum absen via browser. Default: `15` |
| `boost_own_live_viewers` | — | Tiap akun buka browser headless di live kamu (boost penonton). Default: `true` |
| `reply_stagger_min_seconds` | — | Jeda minimum antar akun saat follow+absen. Default: `5` |
| `reply_stagger_max_seconds` | — | Jeda maksimum antar akun. Default: `15` |
| `rate_limit_retry_min_seconds` | — | Tunggu min jika kena error 2008. Default: `15` |
| `rate_limit_retry_max_seconds` | — | Tunggu max jika kena error 2008. Default: `30` |
| `min_poll_interval_seconds` | — | Polling minimum (detik). Default: `2` jika multi akun |
| `verbose_polling` | — | Log detail polling. Default: `false` |
| `use_saved_session` | — | Pakai cookies tanpa login ulang. Default: `false` |

Setting global bisa di-override per akun, misalnya `reply_message` atau `anchor_id` berbeda tiap bot.

### Format single akun (lama, masih didukung)

```json
{
  "anchor_id": "15887479",
  "sm_box_id": "DeyJ...",
  "login": {
    "email": "email@gosh.com",
    "password": "password-kamu"
  },
  "cookies_file": "cookies.json"
}
```

---

## Ambil `sm_box_id` (wajib, sekali)

Gosh membutuhkan token anti-bot dari browser kamu.

### Cara cepat (Console browser)

1. Buka [https://gosh.com](https://gosh.com) di Chrome/Edge
2. Login jika belum
3. Tekan **F12** → tab **Console**
4. Paste dan Enter:

```javascript
localStorage.getItem('pc__sm_box_id')
```

5. Copy string hasilnya (panjang, diawali `DeyJ...`)
6. Tempel ke `config.json`:

```json
"sm_box_id": "DeyJ..."
```

### Panduan interaktif

```bash
python3 get_sm_box_id.py
```

> **Catatan:** `sm_box_id` terikat browser/perangkat. Kalau login gagal (error 1051), ambil ulang dari browser.

---

## Menjalankan bot

### Tes login dulu

```bash
python3 test_login.py
```

| Hasil | Artinya |
|-------|---------|
| `[bot1] OK — login berhasil` | Akun siap jalan |
| `Hasil: 2/2 akun berhasil login` | Semua akun OK |
| Code **1035** | Email/password salah |
| Code **1051** | `sm_box_id` kosong atau expired |

### Jalankan bot

```bash
python3 bot.py
```

Output contoh:

```
13:23:33 [INFO] Menjalankan 2 akun bot
13:23:33 [INFO] [bot1] Memantau komentar https://gosh.com/15887479
13:23:33 [INFO] [bot2] Memantau komentar https://gosh.com/15887479
13:23:40 [INFO] [bot1] Komentar baru dari Phantom[JJ-01] (15815416): halo bang
13:23:41 [INFO] [bot1] Berhasil absen di profil Phantom[JJ-01] (15815416)
13:23:41 [INFO] [bot2] Berhasil absen di profil Phantom[JJ-01] (15815416)
```

Stop bot: **Ctrl+C**

---

## Alur kerja

```
┌─────────────────┐     polling      ┌──────────────────┐
│  Live kamu      │ ◄─────────────── │  bot.py          │
│  (anchor_id)    │   fetch_msg      │  (Python)        │
└─────────────────┘                  └────────┬─────────┘
                                                │
                           komentar baru         │
                                                ▼
                                       ┌──────────────────┐
                                       │ Cek live penonton│
                                       │ (get_by_anchor)  │
                                       └────────┬─────────┘
                                                │
                              penonton live     │
                                                ▼
                                       ┌──────────────────┐
                                       │ tim_send.js      │
                                       │ (Tencent IM)     │
                                       └────────┬─────────┘
                                                │
                                                ▼
                                       ┌──────────────────┐
                                       │ Live penonton    │
                                       │ "absen kak, hadir"│
                                       └──────────────────┘
```

1. Bot polling komentar di channel kamu (default: tanpa jeda)
2. Komen baru terdeteksi → ambil ID penonton
3. Cek apakah penonton **sedang live**
4. Jika live → kirim balasan ke chat live mereka via Tencent IM
5. Cooldown per user nonaktif secara default (balas setiap komen)

---

## Struktur project

```
gosh-bot/
├── bot.py              # Loop utama bot
├── gosh_client.py      # Client API Gosh + login
├── tim_send.js         # Kirim chat via Tencent IM SDK
├── test_login.py       # Tes login
├── get_sm_box_id.py    # Panduan ambil sm_box_id
├── config.example.json # Template config (multi akun)
├── config.json         # Config kamu (git-ignored)
├── cookies_*.json      # Sesi per akun (git-ignored)
├── requirements.txt    # Dependency Python
├── package.json        # Dependency Node.js
└── README.md
```

---

## Troubleshooting

### Login gagal (1035)

- Cek email/password di [gosh.com](https://gosh.com)
- Pastikan akun login via email/password (bukan hanya Google/Apple)

### Login gagal (1051)

- `sm_box_id` kosong atau expired
- Ambil ulang dari browser (lihat langkah di atas)

### Bot jalan tapi tidak ada komen terdeteksi

- Pastikan channel kamu (`anchor_id`) benar
- Coba set `"verbose_polling": true` di config untuk log detail
- Pastikan ada komentar baru di live kamu

### "Berhasil absen" tapi komen tidak muncul

- Pastikan penonton **sedang live** saat bot balas
- Restart bot setelah update terbaru (butuh format chat custom type 10000)
- Cek di live penonton langsung, bukan di live kamu

### "Penonton sedang offline / tidak punya live aktif"

- Penonton tidak sedang streaming → bot tidak bisa kirim chat
- Bot hanya bisa absen di live yang **aktif**

### Error Node.js / npm

```bash
node --version   # harus 12+
npm install      # install ulang dependency
```

---

## Keamanan

**Jangan upload atau share file ini:**

- `config.json` — berisi email, password, sm_box_id semua akun
- `cookies*.json` — berisi token sesi login per akun

Keduanya sudah di-ignore oleh `.gitignore`.

---

## Disclaimer

Automasi chat bisa melanggar Terms of Service Gosh. Gunakan dengan risiko sendiri. Penulis tidak bertanggung jawab atas suspensi akun atau masalah lain.

---

## Upload ke GitHub

Repo lokal sudah siap (`git init` + commit). File rahasia (`config.json`, `cookies.json`) **tidak** ikut ter-upload berkat `.gitignore`.

### Opsi A — GitHub CLI (disarankan)

```bash
cd gosh-bot

# Login GitHub (buka browser)
gh auth login

# Buat repo public dan push sekaligus
gh repo create gosh-bot --public --source=. --remote=origin --push \
  --description "Gosh Live bot — auto-reply absen di live penonton yang komen"
```

### Opsi B — Manual lewat website

1. Buka [github.com/new](https://github.com/new)
2. Nama repo: `gosh-bot` (Public atau Private)
3. **Jangan** centang "Add a README" (sudah ada di lokal)
4. Klik **Create repository**
5. Di terminal:

```bash
cd gosh-bot
git remote add origin https://github.com/USERNAME/gosh-bot.git
git push -u origin main
```

Ganti `USERNAME` dengan username GitHub kamu.

### Update setelah ada perubahan

```bash
git add .
git commit -m "Deskripsi perubahan"
git push
```

---

## Lisensi

MIT
