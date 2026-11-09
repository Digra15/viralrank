# ViralRank

Riset produk viral TikTok untuk affiliator — data diambil dari **TikTok Creative Center**
(endpoint publik, tanpa API key), dengan opsi **TikTok Shop Seller API** dan
**FastMoss** untuk data penjualan/komisi.

## Fitur

- **Radar produk viral** — Creative Center top ads per region (ID/SG/TH), filter periode 7/14/30 hari
- **Skoring** — CTR, CVR, impresi, tren; urut berdasarkan metrik
- **Insight** — brand, industri, hashtag teratas dari set data yang sedang tampil
- **Export CSV** — unduh hasil filter untuk riset lanjutan
- **Akun & peran** — register/login JWT, simpan favorit, alert metrik, catatan
- **Admin panel** — kelola user & peran, konfigurasi API key (FastMoss / TikTok Shop / AI gateway), audit log, snapshot harian
- **AI brief** — ringkasan produk via gateway kompatibel OpenAI (opsional)

## Stack

FastAPI · SQLite · httpx · vanilla JS (tanpa build step) · JWT

## Jalan cepat

```bash
cp .env.example .env          # isi kalau perlu
pip install -r requirements.txt
./run.sh                      # http://localhost:8610
```

Halaman: `/` landing · `/app` dashboard · `/admin` konsol admin.

Admin pertama dibuat otomatis dari `ADMIN_USER` / `ADMIN_PASS` di `.env`.

## Konfigurasi API

Semua kredensial bisa diisi dari **/admin → Konfigurasi API**, tanpa restart:

- `fm_api_key`, `fm_base_url` — FastMoss (opsional; tanpa ini fitur FastMoss nonaktif, data CC tetap jalan)
- `ai_gateway_url`, `ai_gateway_key`, `ai_model_chain` — gateway LLM kompatibel OpenAI
- `cache_ttl` — TTL cache HTTP detik

## Endpoint publik

```
GET  /api/health
GET  /api/ads?period=7&region=ID&limit=20&order_by=ctr
GET  /api/filters
GET  /api/insights?period=7&region=ID
GET  /api/export/csv?period=7&region=ID
GET  /api/fastmoss/rank/topSelling?...
```

## Catatan

- Creative Center tidak butuh key; `anonymous-user-id` UUID v4 + header browser-like wajib.
- Filter `objective=product` sisi server mengembalikan list kosong → filter produk diterapkan
  di sisi klien (`onlyPs`).
- TikTok Shop Seller API butuh app terdaftar di TikTok Developer; selama belum ada,
  hasilnya kosong dan UI jatuh ke data Creative Center.

## Lisensi

MIT
