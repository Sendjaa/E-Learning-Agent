# 🤖 Hermes — Workshop Kerja E-Learning

Hermes adalah asisten akademik otomatis: memantau linimasa E-Learning Moodle, melaporkan tugas ke Telegram, dan menyediakan draf jawaban atas permintaan. Sejak versi modular, Hermes bukan lagi satu skrip — ia adalah **workshop berisi kursi kerja**, di mana setiap kursi memegang satu jenis kerja dengan beban tugasnya sendiri, divisualisasikan di dashboard web.

---

## 🏗️ Arsitektur

Empat proses terpisah berbagi satu database SQLite (`hermes.db`) sebagai antrian dan penyimpanan.

| Proses | Perintah | Tugas |
|---|---|---|
| Bot | `python -m hermes.bot.poller` | Long-poll Telegram: perintah, tombol, sapaan |
| Scraper | `python -m hermes.scraper.run_check` | Buka Moodle, baca linimasa, simpan tugas, lapor |
| Brain | `python -m hermes.brain.worker` | Ambil antrian permintaan jawaban, panggil LLM, kirim draf |
| Dashboard | `python -m hermes.dashboard.server` | Kelas animasi di `http://127.0.0.1:8080` |

```
hermes/
  common/     config, telegram, llm, store (SQLite), report
  roster.py   daftar kursi + pencocokan tugas ke kursi
  scraper/    moodle.py (Playwright), run_check.py
  brain/      worker.py (antrian → LLM → Telegram)
  bot/        poller.py, menu.py
  dashboard/  server.py, static/index.html
```

Database memakai mode WAL dan `busy_timeout` — wajib, karena empat proses menulis bersamaan.

---

## 🚀 Instalasi

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Buat file `.env`:

```bash
# E-Learning Moodle
ELEARNING_URL="https://elearning.itenas.ac.id"
ELEARNING_USERNAME="username_kamu"
PASSWORD="password_kamu"

# Telegram
TELEGRAM_BOT_TOKEN="1234567890:ABCdef..."
TELEGRAM_CHAT_ID="987654321"

# Provider LLM: openrouter (gratis) | deepinfra (berbayar)
LLM_PROVIDER="openrouter"
OPENROUTER_API_KEY="sk-or-v1-..."
LLM_MODEL="google/gemini-2.5-flash:free"

# Opsional
PM_REVIEW=1                # 0 = matikan pemeriksaan PM (hemat 1 panggilan LLM per draf)
CHECK_INTERVAL=7200        # jeda cek linimasa, detik
DASHBOARD_PORT=8080
HERMES_DB="hermes.db"
```

## ▶️ Menjalankan

```bash
./run.sh                            # keempat proses sekaligus (mode uji)
./install.sh --install-service      # systemd: hermes-bot, -scraper, -brain, -dashboard
```

Cek sekali lalu keluar (berguna untuk uji coba):

```bash
python -m hermes.scraper.run_check --once
python -m hermes.brain.worker --once
```

---

## 💬 Perintah Bot

| Perintah | Fungsi |
|---|---|
| `/start`, `/help` | Sapaan dan bantuan |
| `/kelas` | Papan beban tiap agent/kursi |
| `/agent [mata kuliah]` | Daftar tugas yang dipegang satu agent |
| `/cektugas` | Jalankan pengecekan linimasa sekarang |

Tombol **🤖 Minta Jawaban AI** di bawah tiap tugas yang belum dikumpulkan akan memasukkan tugas ke antrian. Agent pemegang mata kuliah itu yang mengerjakan, dan draf dikirim ke Telegram setelah selesai. Draf tidak pernah dikirim ke Moodle otomatis — kamu yang memeriksa dan mengumpulkan.

## 🪑 Roster: Lima Kursi

Isi roster ada di `hermes/roster.py`. Tidak ada mode — semua kursi aktif sekaligus, dan kursi yang tidak kebagian tugas tampil kosong di dashboard. Tugas kuliah dan pekerjaan proyek klien jalan bersamaan.

| Kursi | Kerja |
|---|---|
| Programmer | kode, API, database, algoritma, jaringan |
| UI/UX | wireframe, alur pemakaian, desain antarmuka, aksesibilitas |
| Tester | skenario uji, kasus batas, regresi, cara reproduksi bug |
| Senja (PM) | memeriksa hasil kerja keempat kursi lain, plus kebutuhan klien dan estimasi |
| Senja (Kuliah) | semua tugas kuliah yang tidak masuk kursi lain |

Kamu pegang dua kursi: kuliah (yang kamu kumpulkan sendiri) dan PM (yang memutuskan LOLOS/REVISI).

Jumlahnya lima karena tiap kursi mewakili jenis kerja yang berbeda domainnya, dan satu kursi tidak boleh mengerjakan sekaligus memeriksa pekerjaan yang sama. Kalau volume pekerjaan proyek kecil, bisa diringkas: buang UI/UX ke Programmer (jadi 4 kursi), atau buang Tester ke Programmer juga (jadi 3) — yang terakhir paling berisiko, karena tidak ada lagi yang menguji kerja sendiri.

**Pencocokan tugas.** Tugas dicocokkan lewat `kata_kunci` (huruf kecil, dicocokkan ke nama mata kuliah atau nama pekerjaan). Kata kunci 3 huruf atau kurang harus cocok sebagai kata utuh — jadi `uji` tidak nyangkut di "Ujian Tengah Semester", dan `pm` tidak nyangkut di "Pengabdian Masyarakat". Urutan di list menentukan prioritas, jadi taruh yang paling spesifik di atas.

Kursi terakhir wajib bertanda `["*"]` sebagai penampung. Kalau tidak, tugas yang tidak dikenali siapa pun jatuh ke kursi terakhir yang kebetulan ada di list — dan jawabannya muncul dengan gaya kerja yang salah.

Mengubah roster: edit `ROSTER` di `hermes/roster.py`. Satu entri:

```python
{
    "nama": "Programmer",
    "blok": "Blok Proyek Klien",          # kursi dalam blok yang sama ditata berdekatan
    "mata_kuliah": "kode dan sistem",     # label yang tampil di kelas dan Telegram
    "kata_kunci": ["api", "backend", "bug"],
    "prompt": "Kamu programmer. Untuk tugas pemrograman, hasilkan kode ...",
}
```

Tambahkan `"pm": True` pada satu entri untuk menjadikannya kursi pemeriksa. Cuma satu yang boleh bertanda itu — kalau tidak ada, tidak ada pemeriksaan.

Aturan pencocokan punya self-check — jalankan `python -m hermes.roster` setelah mengedit.

Beban tiap kursi dihitung dari data nyata — jumlah tugas belum dikumpulkan, dibobot urgensi tenggat (default: <24 jam = 3, <72 jam = 2, sisanya = 1). Ambang dan bobotnya bisa disetel lewat `URGENT_HOURS`, `SOON_HOURS`, `WEIGHT_*` di `.env`.

### 🔍 Pemeriksaan PM

Kalau ada kursi bertanda `"pm": True`, ia memeriksa tiap draf yang selesai dikerjakan kursi lain. Hasil pemeriksaan dikirim ke Telegram terpisah — keputusan `LOLOS` atau `PERLU REVISI`, plus apa yang masih kurang. Kursi yang memeriksa dirinya sendiri tidak diperiksa ulang.

Pemeriksaan ini satu panggilan LLM tambahan per draf. Matikan dengan `PM_REVIEW=0` kalau kuota menipis. Hasilnya disimpan di tabel `ulasan` dan dihitung sebagai beban kerja kursi PM, jadi angkanya naik di dashboard setelah PM mulai memeriksa. PM tidak mengubah draf siapa pun — perbaikan tetap keputusanmu.

## 🖥️ Dashboard

Buka `http://127.0.0.1:8080`. Tampilannya berupa workshop: lantai beton epoksi, langit-langit gelap, lampu gantung industri, papan alat di dinding, lemari peralatan beroda, dan tumpukan peti. Tiap kursi menampilkan agent, mata kuliah, jumlah tugas, dan bar beban; avatar bergerak makin cepat ketika beban agent makin berat.

Ruangan dibagi jadi **blok**: kursi dikelompokkan menurut field `blok` di roster. Tiap blok dapat zona lantai bercat sendiri dengan marka kuning, papan alat sendiri, dua lampu gantung, label nama blok, dan dipisah sekat rendah setinggi 1.45 m — sedikit di atas kepala orang yang duduk, jadi tiap blok terbaca sebagai bilik kerja sendiri tanpa menutup ruangan. Kursi di dalam satu blok ditata sebagai grid maksimal 2 kolom. Jumlah blok bebas: tambah nilai `blok` baru di roster dan ruangan menata ulang sendiri.

**Kursi kosong tidak berdiam di mejanya.** Kursi yang tidak memegang satu tugas pun berdiri, berjalan ke pojok santai di depan ruangan, lalu duduk di beanbag sambil main game — lengkap dengan pengendali yang menyala di tangan, dan namanya diberi tanda `· santai` di ruangan maupun di sidebar. Pojok santai (karpet, beanbag, lampu, peti) baru dibangun kalau memang ada kursi yang menganggur. Begitu tugas masuk ke kursi itu, orangnya berjalan kembali ke meja dan mulai mengetik. Layar monitor di meja tanpa tugas ikut dimatikan, jadi kelihatan sekilas meja mana yang tidak dipakai.

**Isi ruangan.** Dinding belakang bertekstur beton ekspos dengan nat bekisting, jendelanya memakai pemandangan luar yang digambar di kanvas (langit, siluet gedung, jalan), lalu ditambah rak buku, dua poster diagram di atas papan alat, tiga tanaman pot di sudut, dan tiap meja punya kabel menjuntai dari monitor ke lantai plus tempat pensil. Tiap lampu gantung memancarkan genangan cahaya di lantai lewat bidang bergradasi radial (additive) — bukan lampu kedua, jadi tidak menambah beban hitungan cahaya. Model karakter low-poly: mata, hidung, kerah, ikat pinggang, dan pengendali game saat santai.

Kalau roster diubah sampai jumlah bloknya bukan dua lagi, rak buku di tengah dinding (`rakDinding(0, 1.7)`) bisa bertabrakan dengan papan alat blok yang baru — pindahkan x-nya di `bangunRuangan()`.

Server hanya bind ke localhost karena halaman ini memuat link tugas dan data akademik. Untuk mengakses dari luar, pakai SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 user@server
```

**Kendali:**

| Aksi | Efek |
|---|---|
| Geser di ruangan | memutar kamera |
| Scroll | zoom (jarak 2–24 m) |
| Klik orang / nama di sidebar | pilih kursi, kamera terbang halus ke depannya |
| **F** | fokus ulang kamera ke kursi terpilih |
| **M** | mode malam — matahari redup, lampu gantung menyala terang |
| Tombol **⛶ Layar penuh** | seluruh halaman masuk layar penuh (Esc untuk keluar) |

Sidebar kiri memuat daftar kursi dikelompokkan per blok, dengan titik warna yang sama dengan zona lantainya. Klik nama di situ sama dengan klik orang di ruangan.

---

## 🛠️ Catatan Perawatan

- **Selector Moodle rapuh.** Kalau linimasa tidak terbaca, Hermes menyimpan `debug_linimasa.html` untuk diperiksa, dan `hermes/scraper/moodle.py` adalah satu-satunya tempat yang perlu diubah.
- **Kuota LLM gratis terbatas** (OpenRouter gratis ±50 request/hari). Jawaban hanya dibuat saat tombol diklik, bukan untuk semua tugas sekaligus.
- **Troubleshooting multi-proses:** kalau muncul `database is locked`, pastikan semua proses mengakses SQLite lewat `hermes/common/store.py` (di sanalah WAL dan busy_timeout diatur).

## ⚠️ Catatan Penggunaan

Proyek ini dibuat untuk membantu produktivitas akademik personal. Periksa, edit, dan pahami setiap draf sebelum mengumpulkannya ke sistem penilaian.
