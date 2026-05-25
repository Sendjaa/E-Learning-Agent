# 🤖 Hermes E-Learning Agent

Hermes adalah asisten akademik otomatis berbasis Python yang mengintegrasikan sistem E-Learning Moodle (Itenas) dengan Telegram Bot dan kecerdasan buatan (LLM). 

Agent ini akan memantau linimasa tugas aktif kamu setiap 2 jam sekali, melaporkan detail tenggat waktu ke Telegram, dan menyediakan tombol interaktif untuk merumuskan draf jawaban tugas kuliah menggunakan model AI terbaik secara **on-demand** (hanya saat diminta).

---

## ✨ Fitur Utama

* **🔄 Automated E-Learning Scraping:** Masuk dan membaca widget Linimasa (Timeline) Moodle secara berkala menggunakan Playwright (Headless Chromium).
* **🔔 Telegram Smart Report:** Mengirimkan laporan detail mengenai judul tugas, mata kuliah, sisa waktu, dan ringkasan instruksi soal dengan format HTML yang rapi.
* **🧠 On-Demand AI Solutions (Fitur Baru):** AI tidak akan langsung membuat jawaban otomatis untuk menghemat kuota. Tombol **"🤖 Minta Jawaban AI"** akan muncul di bawah laporan, dan draf jawaban baru dibuat ketika tombol tersebut diklik.
* **🛠️ Robust Failover System:** Dilengkapi dengan mekanisme penanganan error *Browser Disconnected*, deteksi *Rate Limit* (429), serta otomatis beralih (*fallback*) ke model gratis OpenRouter lain jika model utama sedang sibuk atau mati (404/400).

---

## 🚀 Panduan Instalasi

### 1. Prasyarat Sistem
Pastikan perangkat atau server kamu sudah terinstal:
* Python 3.8 atau versi di atasnya
* Pip (Python Package Installer)

### 2. Kloning & Pemasangan Dependensi
Buka terminal/command prompt di folder proyek kamu, lalu jalankan perintah berikut:

```bash
# Instal library yang dibutuhkan
pip install python-dotenv requests openai playwright

# Instal driver browser Chromium untuk Playwright
playwright install chromium
```

3. Konfigurasi Environment (.env)
Buat sebuah file bernama .env di direktori utama proyek kamu, lalu isi dengan konfigurasi berikut:

```bash
# URL dan Akun E-Learning Moodle
ELEARNING_URL="[https://elearning.itenas.ac.id](https://elearning.itenas.ac.id)"  # Sesuaikan jika rute URL berbeda
ELEARNING_USERNAME="USERNAME_KAMU"
PASSWORD="PASSWORD_KAMU"
```

# Konfigurasi Telegram Bot
```bash
TELEGRAM_BOT_TOKEN="1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ"
TELEGRAM_CHAT_ID="987654321"
```

# Konfigurasi Provider LLM AI
# Pilihan provider: openrouter (gratis/rekomendasi) | deepinfra (berbayar)
LLM_PROVIDER="openrouter"
OPENROUTER_API_KEY="sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx"

# Model Utama (Bisa disesuaikan dengan integrasi provider key kamu)
LLM_MODEL="google/gemini-2.5-flash:free"

🛠️ Cara Menjalankan Bot
Untuk menjalankan Agent Hermes, kamu hanya perlu mengeksekusi file script utamanya (misal bernama bot.py):
```bash
python bot.py
```
Setelah dijalankan:
Thread 1 (Telegram Polling): Akan langsung aktif di latar belakang untuk mendengarkan instruksi klik tombol dari ruang obrolan Telegram kamu.
Thread 2 (Moodle Scraper): Akan langsung melakukan pengecekan pertama ke akun E-Learning kamu, kemudian masuk ke mode tidur (sleep) selama 2 jam sebelum melakukan pengecekan berikutnya secara terus-menerus.

📊 Alur Kerja Sistem
```bash
[ Moodle E-Learning ] 
        │
        ▼ (Scraping Headless tiap 2 jam)
 [ Playwright Engine ] ───> Kirim Laporan Tugas ───> [ Telegram Chat ]
                                                            │
                                             (Klik: 🤖 Minta Jawaban AI)
                                                            │
                                                            ▼
 [ Draf Jawaban Dikirim ] <─── Proses Soal <─── [ OpenRouter API (LLM) ]
```

 💡 Tips Penggunaan Aman (Anti Rate-Limit 429)
Karena OpenRouter membatasi kuota harian akun gratis standar sebanyak 50 requests, sangat direkomendasikan untuk menyambungkan Provider Key kamu sendiri (seperti Google AI Studio atau Hugging Face) di menu OpenRouter Integrations. Dengan begitu, kamu bisa menikmati ribuan requests gratis tanpa terkena pembatasan rate-limit harian.

📝 Catatan Lisensi
Proyek ini dibuat untuk tujuan membantu produktivitas akademik personal. Pastikan untuk tetap meninjau, mengedit, dan mempelajari kembali setiap draf jawaban yang dihasilkan oleh AI sebelum mengumpulkannya ke sistem penilaian.
