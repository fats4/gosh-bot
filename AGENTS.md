# Panduan Agent — Gosh Live Bot

Dokumen ini untuk **AI agent / Cursor agent** yang mengerjakan repo ini tanpa konteks chat sebelumnya. Ikuti urutan di bawah saat user minta setup, ubah anchor, proxy, atau jalankan bot.

## Repo singkat

- **CLI utama:** `gosh.py` (menu interaktif + subcommand)
- **Runtime bot:** `bot.py` → `run_bot()`
- **Config:** `config.json` ( **git-ignored** — jangan commit)
- **Template:** `config.example.json`

```bash
cd /path/to/gosh-bot
pip install -r requirements.txt
npm install
cp config.example.json config.json   # jika belum ada
python3 gosh.py config validate
```

---

## Yang wajib dari user (jangan commit)

| Item | Cara isi |
|------|----------|
| `sm_box_id` | Browser Gosh → Console: `localStorage.getItem('pc__sm_box_id')` |
| `accounts[].login` | Email **Gmail/common** (Gosh menolak banyak domain disposable, mis. `@grmill.com` code 1077) |
| `accounts[].anchor_id` | ID numerik channel live (lihat preset atau API di bawah) |
| Proxy (opsional) | `proxies.txt` + `proxy_username` / `proxy_password` |

**Jangan** push: `config.json`, `proxies.txt`, `cookies_*.json`, `*.bak`.

---

## Perintah yang agent harus pakai

```bash
python3 gosh.py status              # bot jalan? anchor? jumlah akun?
python3 gosh.py config validate     # config lengkap?
python3 gosh.py login test          # tes login semua akun aktif
python3 gosh.py config proxy test   # tes proxy (407 = auth/plan expired)
python3 gosh.py run -d              # background → bot.log
python3 gosh.py stop                # stop bot + browser_watch
tail -f bot.log
grep "live/join OK" bot.log         # boost viewer berhasil
```

---

## Preset anchor (CLI)

Daftar resmi ada di `gosh.py` → `ANCHOR_PRESETS`. Saat menambah profil baru, **update `ANCHOR_PRESETS`** dan baris ini.

| ID | Label |
|----|--------|
| 15887479 | Gameshunter / Faats_KNJ05 |
| 16436304 | Zeel_JJ05 |
| 16358724 | Sirenia_JJ05 |
| 16358511 | Moree_JJ05 |
| 16349669 | Yonjix_JJ05 |
| 16020021 | Jayden_KNJ05 |
| 16453888 | Fumgump_KNJ05 |
| 16555919 | jacobbb_KNJ05 |
| 16616188 | F0lkzz_KNJ05 |

**Ganti anchor semua akun + jalankan:**

```bash
python3 gosh.py run -a 16436304 -d
# atau interaktif: python3 gosh.py run  → pilih nomor
python3 gosh.py run -d --use-config-anchor   # tanpa prompt, pakai config
```

**Profil pakai nickname (bukan angka):** resolve `uid` lewat API:

```python
from gosh_client import GoshClient
from pathlib import Path
c = GoshClient(cookies_file="cookies_bot1.json", load_cookies=Path("cookies_bot1.json").exists())
room = c.get_live_by_anchor("F0lkzz_KNJ05")  # atau slug show_id
anchor_id = str(room["uid"])  # contoh: 16616188
```

Lalu set `anchor_id` di semua entry `accounts` di `config.json`, atau tambah ke `ANCHOR_PRESETS` + `run -a`.

---

## Resep config umum (global di `config.json`)

### Mode boost viewer saja (tanpa reply komentar)

```json
"auto_reply_on_comment": false,
"boost_own_live_viewers": true,
"boost_viewer_use_proxy": false,
"boost_viewer_sequential": true,
"auto_follow_anchor": true,
"watch_before_comment_seconds": 0
```

### Mode absen + reply komentar (default lama)

```json
"auto_reply_on_comment": true,
"boost_own_live_viewers": true,
"watch_before_comment_seconds": 15
```

### Nonaktifkan proxy (VPS langsung)

```json
"proxy_list_file": "",
"boost_viewer_use_proxy": false
```

Hapus field `"proxy"` dari tiap akun jika perlu.

### Aktifkan proxy login/API

1. Isi `proxies.txt` (satu `host:port` per baris)
2. Set `proxy_username`, `proxy_password`, `proxy_list_file": "proxies.txt"`
3. Jalankan:

```bash
python3 gosh.py config proxy from-file
python3 gosh.py config proxy test
```

**Boost viewer:** default **tanpa proxy** (VPS langsung) karena `live/join` lebih stabil. Eksperimental: `"boost_viewer_use_proxy": true`.

---

## Operasi config via Python (agent)

```python
import json
from pathlib import Path
from setup_config import load_config, save_config, sync_proxies_from_file

path = Path("config.json")
cfg = load_config(path)

# Ganti anchor semua akun
anchor = "16358511"
for acc in cfg.get("accounts") or []:
    acc["anchor_id"] = anchor

# Nonaktifkan akun tanpa hapus
acc["enabled"] = False  # resolve_accounts() skip jika false

# Hapus akun domain yang ditolak Gosh
cfg["accounts"] = [
    a for a in cfg["accounts"]
    if not str(a.get("login", {}).get("email", "")).lower().endswith("@grmill.com")
]

save_config(path, cfg)
# sync_proxies_from_file(cfg, save_path=path)
```

---

## Batasan teknis (jangan dilanggar tanpa alasan)

1. **Penonton live naik** hanya jika browser POST **`/gosh_base/app/live/join`** sukses → log: `Viewer live sendiri terdaftar (live/join OK)`.
2. **Browser boost** di `gosh_client.start_own_live_viewer()` — proxy default off.
3. **Multi-akun:** default **boost antrian** (`boost_viewer_sequential: true`) — satu browser join sampai `live/join OK`, baru akun berikutnya. ~8–10 akun di VPS 4 core / 8 GB lebih stabil.
4. Setelah `stop` bot, cek sisa: `pgrep -af browser_watch_keep` — jika ada, `python3 gosh.py stop`.

---

## Alur kerja agent (checklist)

1. `python3 gosh.py status` + `config validate`
2. Pastikan `config.json` ada dan `sm_box_id` terisi
3. `python3 gosh.py login test` — hapus/nonaktifkan akun gagal
4. Terapkan permintaan user (anchor / proxy / mode boost-only)
5. `python3 gosh.py stop` lalu `run -d` jika user minta jalan
6. Verifikasi log: login OK, follow anchor (jika aktif), `live/join OK`

---

## Troubleshooting cepat

| Gejala | Penyebab | Tindakan |
|--------|----------|----------|
| Login ProxyError / 407 | Proxy mati atau salah password | `config proxy test`, curl `-x`, matikan proxy sementara |
| Login 1077 Unsupported email | Domain email ditolak | Hapus akun atau ganti email |
| Login 1051 | `sm_box_id` expired | User ambil ulang dari browser |
| `live/join belum terkonfirmasi` | CPU/RAM penuh atau live offline | Kurangi akun, stagger, cek live online |
| Bot STOP tapi RAM tinggi | Sisa `browser_watch_keep.js` | `python3 gosh.py stop` |

---

## Git

- Commit hanya kode + `config.example.json`, **bukan** `config.json`.
- Remote contoh: `https://github.com/fats4/gosh-bot.git`

User docs: [README.md](README.md)
