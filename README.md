# Gosh Live Bot — Absen Otomatis

Bot Python untuk [Gosh Live](https://gosh.com) yang memantau komentar di channel live kamu, lalu otomatis membalas **"absen kak, hadir"** di **live penonton yang komen**.

Contoh: seseorang komen di live kamu → bot masuk ke live mereka → kirim `"absen kak, hadir"`.

---

## Fitur

- Pantau komentar baru di channel kamu (polling terpusat untuk multi akun)
- Deteksi komentar teks **dan emoji custom Gosh** (`[emoji:id]`)
- **Multi akun** — banyak bot dalam 1 config, jalan paralel
- **Proxy per akun** — IP berbeda via ProxyScrape / HTTP proxy
- **Browser watch** — daftar sebagai penonton (boost viewer count)
- Balasan acak dari template (`{from_name}`)
- Jeda antar akun (stagger) anti rate-limit
- Skip komentar dari akun bot fleet sendiri
- Login email/password via API Gosh + Tencent IM SDK

---

## Persyaratan

| Software | Versi minimum | Fungsi |
|----------|---------------|--------|
| **Python** | 3.10+ | Bot utama + CLI |
| **Node.js** | 12+ | Chat + browser watch (Puppeteer) |
| **npm** | 8+ | `@tencentcloud/chat`, `puppeteer` |
| **Akun Gosh** | — | Email + password per bot |

---

## Instalasi cepat

```bash
git clone https://github.com/fats4/gosh-bot.git
cd gosh-bot
pip install -r requirements.txt
npm install
python3 gosh.py          # menu interaktif — pilih Setup config
```

---

## CLI all-in-one (`gosh.py`)

Jalankan tanpa argumen untuk menu interaktif:

```bash
python3 gosh.py
```

```
  1. Jalankan bot (foreground)
  2. Jalankan bot (background)
  3. Hentikan bot
  4. Status bot & config
  5. Setup config
  6. Tes login semua akun
  7. Tes proxy
  0. Keluar
```

### Setup config (menu 5)

| Pilihan | Fungsi |
|---------|--------|
| **1. Setup cepat** | sm_box_id + anchor + tempel email + proxy file |
| **2. Update config** | Ganti sm_box / proxy / password saja |
| **3. Sync proxy** | Baca ulang `proxies.txt` → assign ke akun |
| **4. Cek status** | Validasi config |
| **5. Lihat config** | Tampilkan config (password di-mask) |
| **6. Warna chat** | Atur warna nickname per akun bot |

### Perintah langsung

```bash
python3 gosh.py run              # jalankan bot
python3 gosh.py run -d           # background (log → bot.log)
python3 gosh.py stop             # hentikan bot + browser
python3 gosh.py status           # status bot & config
python3 gosh.py login test       # tes login semua akun
python3 gosh.py config quick     # setup cepat
python3 gosh.py config proxy from-file   # sync proxy dari txt
python3 gosh.py config colors            # menu warna chat akun
python3 gosh.py config colors auto       # auto-assign warna berbeda
python3 gosh.py config colors set asisten1 "#FF6D1C"
python3 gosh.py config proxy test        # tes koneksi proxy
python3 gosh.py config validate
```

---

## Setup config cepat

### Langkah 1 — Buat config

```bash
cp config.example.json config.json
python3 gosh.py
# Pilih 5 → 1 (Setup cepat)
```

Wizard 4 langkah:

1. **sm_box_id** — dari browser (lihat bawah)
2. **Anchor ID** — ID channel live kamu
3. **Email** — tempel 1 email per baris (password sama untuk semua)
4. **Proxy** — dari file `proxies.txt` (opsional)

### Langkah 2 — Proxy dari ProxyScrape

Buat file `proxies.txt` (boleh 100+ baris, bot pakai 1 proxy per akun):

```
216.26.232.63:3129
65.111.1.61:3129
209.50.160.10:3129
...
```

Upload ke VPS:

```bash
scp ~/Downloads/proxyscrape_premium_http_proxies.txt root@IP_VPS:/root/gosh-bot/proxies.txt
```

Isi credential di `config.json`:

```json
"proxy_list_file": "proxies.txt",
"proxy_username": "USERNAME_PROXYSCRAPE",
"proxy_password": "PASSWORD_PROXYSCRAPE"
```

Sync ke akun:

```bash
python3 gosh.py config proxy from-file
```

| Akun | Proxy |
|------|-------|
| asisten1 | baris 1 |
| asisten2 | baris 2 |
| ... | ... |

Bot otomatis baca `proxies.txt` setiap kali dijalankan.

---

## Ambil `sm_box_id` (wajib, sekali)

1. Buka [https://gosh.com](https://gosh.com) di Chrome/Edge
2. **F12** → **Console** → paste:

```javascript
localStorage.getItem('pc__sm_box_id')
```

3. Copy string `DeyJ...` ke config

```bash
python3 gosh.py sm-box              # panduan
python3 gosh.py config set-sm-box "DeyJ..."
```

---

## Format config

```json
{
  "reply_from_name": "Faats [KNJ 05]",
  "randomize_reply": true,
  "skip_fleet_accounts": true,
  "auto_follow_on_comment": false,
  "watch_before_comment_seconds": 15,
  "boost_own_live_viewers": true,
  "reply_stagger_min_seconds": 5,
  "reply_stagger_max_seconds": 15,
  "min_poll_interval_seconds": 2,
  "proxy_list_file": "proxies.txt",
  "proxy_username": "USERNAME_PROXYSCRAPE",
  "proxy_password": "PASSWORD_PROXYSCRAPE",
  "sm_box_id": "DeyJ...",
  "accounts": [
    {
      "name": "asisten1",
      "anchor_id": "15887479",
      "proxy": "http://user:pass@1.2.3.4:3129",
      "login": {
        "email": "akun1@gmail.com",
        "password": "password-akun1"
      },
      "cookies_file": "cookies_bot1.json"
    }
  ]
}
```

| Field | Wajib | Keterangan |
|-------|-------|------------|
| `accounts` | ✅ | Array akun bot |
| `accounts[].name` | — | Nama log. Default: `asisten1`, `asisten2`, ... |
| `accounts[].anchor_id` | ✅ | ID channel yang dipantau |
| `accounts[].login` | ✅ | Email + password Gosh |
| `accounts[].proxy` | — | HTTP proxy per akun (auto dari `proxies.txt`) |
| `accounts[].chat_name_color` | — | Warna nickname di chat live (hex, mis. `#FF6D1C`). Auto beda tiap akun jika kosong |
| `sm_box_id` | ✅ | Token browser anti-bot |
| `proxy_list_file` | — | Path file proxy (default: `proxies.txt`) |
| `proxy_username` | — | Username ProxyScrape (jika proxy format `host:port`) |
| `proxy_password` | — | Password ProxyScrape |
| `skip_fleet_accounts` | — | Lewati komen dari akun bot sendiri. Default: `true` |
| `boost_own_live_viewers` | — | Browser headless boost penonton live sendiri |
| `watch_before_comment_seconds` | — | Nonton live dulu sebelum absen (detik) |
| `reply_stagger_*` | — | Jeda acak antar akun per komentar |

Setting global bisa di-override per akun.

---

## Menjalankan bot

```bash
# Tes login dulu
python3 gosh.py login test

# Jalankan
python3 gosh.py run

# Background (VPS)
python3 gosh.py run -d
python3 gosh.py stop
```

Log contoh:

```
18:17:48 [INFO] Menjalankan 8 akun bot
18:17:48 [INFO] Proxy dari proxies.txt: 8 akun ← 8 proxy (file punya 100 unik)
18:17:48 [INFO] [asisten1] Komentar baru dari PenontonX...
18:17:48 [INFO] [asisten2] Jeda 7.3s sebelum aksi (antrian akun ke-2)
18:18:05 [INFO] [asisten1] Berhasil absen di profil PenontonX...
```

---

## Alur kerja

```
Live kamu (anchor_id)
       │ polling terpusat (asisten1)
       ▼
  Komentar baru ──► broadcast ke 8 akun
       │
       ├── browser watch 15s (live penonton)
       ├── kirim absen via TIM (tim_send.js)
       └── boost viewer live sendiri (browser_watch_keep.js)
```

---

## Struktur project

```
gosh-bot/
├── gosh.py                 # CLI all-in-one + menu interaktif
├── bot.py                  # Bot multi-akun
├── gosh_client.py          # API Gosh + browser watch
├── setup_config.py         # Setup & kelola config
├── tim_send.js             # Kirim chat Tencent IM
├── tim_watch.js            # Watch via TIM
├── browser_watch.js        # Browser watch sementara (15s)
├── browser_watch_keep.js   # Browser watch persisten (boost viewer)
├── proxy_helper.js         # Helper proxy Puppeteer
├── test_login.py           # Tes login
├── get_sm_box_id.py        # Panduan sm_box_id
├── config.example.json     # Template config
├── proxies.txt             # Daftar proxy (git-ignored)
├── config.json             # Config kamu (git-ignored)
└── cookies_*.json          # Sesi per akun (git-ignored)
```

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Login gagal **1035** | Email/password salah |
| Login gagal **1051** | `sm_box_id` expired — ambil ulang |
| Login gagal **2008** | Rate limit — bot auto-retry + stagger antar akun |
| Hanya 1 akun yang absen | Pastikan versi terbaru (shared comment feed) |
| Viewer tidak naik | Butuh browser watch (Puppeteer), bukan API saja |
| Proxy gagal | `python3 gosh.py config proxy test` |
| Sync proxy error | Upload `proxies.txt`, cek `proxy_username/password` |

```bash
node --version   # harus 12+
npm install      # install ulang jika puppeteer error
```

---

## Keamanan

**Jangan upload atau share:**

- `config.json` — email, password, sm_box_id, proxy credential
- `proxies.txt` — daftar proxy
- `cookies_*.json` — token sesi login

Semua sudah di-ignore oleh `.gitignore`.

---

## Disclaimer

Automasi chat bisa melanggar Terms of Service Gosh. Gunakan dengan risiko sendiri.

---

## Lisensi

MIT
