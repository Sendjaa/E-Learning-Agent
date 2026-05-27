import os
import re
import time
from datetime import datetime
import requests
from openai import OpenAI
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv

# Memuat environment variables dari file .env (path absolut, cross-platform)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_SCRIPT_DIR, ".env"))

# --- 1. KONFIGURASI ---
def _env(key, default=""):
    val = os.getenv(key, default)
    return val.strip().strip('"').strip("'") if val else default


# Provider: openrouter = DeepSeek gratis | deepinfra = berbayar
LLM_PROVIDER = _env("LLM_PROVIDER", "openrouter").lower()

if LLM_PROVIDER == "deepinfra":
    LLM_API_KEY = _env("HERMES_API_KEY") or _env("DEEPINFRA_API_KEY")
    LLM_MODEL = _env("HERMES_MODEL") or _env("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2-Exp")
    LLM_BASE_URL = _env("HERMES_BASE_URL") or _env("LLM_BASE_URL", "https://api.deepinfra.com/v1/openai")
    _llm_headers = None
else:
    LLM_API_KEY = _env("OPENROUTER_API_KEY") or _env("HERMES_API_KEY")
    LLM_MODEL = _env("LLM_MODEL") or _env("HERMES_MODEL", "google/gemini-2.5-flash:free")
    LLM_BASE_URL = _env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    _llm_headers = {
        "HTTP-Referer": _env("OPENROUTER_REFERER", "https://github.com/assistant-hermes"),
        "X-Title": "Hermes E-Learning Agent",
    }

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ELEARNING_URL = (os.getenv("ELEARNING_URL") or "").rstrip("/")
ELEARNING_USERNAME = (os.getenv("ELEARNING_USERNAME") or "").strip()
ELEARNING_PASSWORD = (os.getenv("PASSWORD") or "").strip()

_client_kwargs = {"api_key": LLM_API_KEY, "base_url": LLM_BASE_URL}
if _llm_headers:
    _client_kwargs["default_headers"] = _llm_headers
client = OpenAI(**_client_kwargs)

# Menggunakan model-model gratis terbaru yang valid & diintegrasikan dengan key sendiri
OPENROUTER_FALLBACK_MODELS = [
    "NVIDIA: Nemotron 3 Nano 30B A3B/free",
    "openrouter/free"
]
LAST_LLM_MODEL_USED = LLM_MODEL

# --- 2. FUNGSI TELEGRAM ---
TELEGRAM_MAX_LEN = 4096

def escape_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pecah_pesan(teks, batas):
    sisa = teks
    bagian = []
    while len(sisa) > batas:
        potong = sisa.rfind("\n", 0, batas)
        if potong < batas // 2:
            potong = batas
        bagian.append(sisa[:potong])
        sisa = sisa[potong:].lstrip("\n")
    if sisa:
        bagian.append(sisa)
    return bagian


def send_telegram_message(message, parse_mode="HTML", reply_markup=None, chat_id=None):
    """Kirim pesan Telegram; mendukung tombol inline keyboard dan chat_id custom."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    batas = 3900 if parse_mode else TELEGRAM_MAX_LEN
    semua_ok = True
    target_chat = chat_id if chat_id else TELEGRAM_CHAT_ID

    chunks = _pecah_pesan(message, batas)
    for idx, bagian in enumerate(chunks):
        payload = {"chat_id": target_chat, "text": bagian}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        # Tempelkan tombol hanya di potongan pesan terakhir
        if reply_markup and idx == len(chunks) - 1:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 400 and parse_mode:
                payload.pop("parse_mode", None)
                response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            semua_ok = False
            print(f"[Telegram Error] Gagal mengirim: {e}")
    return semua_ok


def kirim_analisis_jawaban(nama_t, link_t, jawaban):
    if not jawaban or not jawaban.strip():
        jawaban = "(Model tidak mengembalikan jawaban.)"

    header = (
        "🚨 <b>ANALISIS JAWABAN TUGAS</b>\n\n"
        f"📌 <b>Tugas:</b> {escape_html(nama_t)}\n"
        f"🔗 <b>Link:</b> {link_t}\n"
        f"🤖 <b>Model:</b> {escape_html(LAST_LLM_MODEL_USED)}"
    )
    if not send_telegram_message(header):
        return False

    potongan = _pecah_pesan(jawaban.strip(), 3500)
    total = len(potongan)
    for i, bagian in enumerate(potongan, start=1):
        label = "📝 <b>DRAF JAWABAN AI:</b>"
        if total > 1:
            label += f" <i>(bagian {i}/{total})</i>"
        isi = f"{label}\n<pre>{escape_html(bagian)}</pre>"
        if not send_telegram_message(isi):
            return False

    footer = "<i>Silakan periksa kembali draf di atas sebelum dikumpulkan.</i>"
    return send_telegram_message(footer)


def parse_timeline_item(item):
    link = item.locator("a[href*='mod/assign']").first
    nama = item.locator("h6.event-name").first.inner_text().strip()
    if not nama:
        nama = link.inner_text().strip()
    if nama.endswith(" is due"):
        nama = nama[:-8].strip()

    mata_kuliah = item.locator("small.text-muted").first.inner_text().strip()
    jam_tenggat = item.locator("small.text-right").first.inner_text().strip()

    aria = link.get_attribute("aria-label") or link.get_attribute("title") or ""
    tenggat_penuh = ""
    match = re.search(r"jatuh tempo pada (.+)$", aria, re.IGNORECASE)
    if match:
        tenggat_penuh = match.group(1).strip()

    link_tugas = link.get_attribute("href") or ""
    link_submit = ""
    submit_link = item.locator("a[href*='action=editsubmission']")
    if submit_link.count():
        link_submit = submit_link.first.get_attribute("href") or ""

    icon_alt = item.locator("img.icon").first.get_attribute("alt") or "Tugas"

    return {
        "nama": nama,
        "mata_kuliah": mata_kuliah,
        "jam_tenggat": jam_tenggat,
        "tenggat_penuh": tenggat_penuh,
        "jenis_aktivitas": icon_alt,
        "link_tugas": link_tugas,
        "link_submit": link_submit,
        "aria_label": aria,
    }


def ambil_detail_tugas(page, link_tugas):
    page.goto(link_tugas, timeout=60000)
    page.wait_for_load_state("domcontentloaded")

    baris = [
        b.strip()
        for b in page.locator("#region-main").inner_text().split("\n")
        if b.strip()
    ]
    judul = baris[0] if baris else ""

    status = {}
    rows = page.locator(".submissionstatustable tr, table.generaltable tr")
    for i in range(rows.count()):
        row = rows.nth(i)
        cells = row.locator("th, td")
        if cells.count() >= 2:
            key = cells.nth(0).inner_text().strip()
            val = cells.nth(1).inner_text().strip()
            if key:
                status[key] = val

    ringkasan_soal = ""
    for sel in ["#intro .no-overflow", "#intro", ".box.generalbox .no-overflow"]:
        loc = page.locator(sel).first
        if loc.count() and loc.is_visible():
            ringkasan_soal = loc.inner_text().strip()
            if ringkasan_soal:
                break

    # Simpan instruksi asli yang panjang untuk pemrosesan AI nanti
    instruksi_penuuh = page.locator("#region-main").inner_text()

    if len(ringkasan_soal) > 280:
        ringkasan_soal = ringkasan_soal[:280].rstrip() + "…"

    content_lower = page.content().lower()
    belum_dikumpulkan = any(
        x in content_lower
        for x in ("belum dikumpulkan", "belum di kumpulkan", "belum mengirim", "tidak ada upaya")
    )

    return {
        "judul": judul,
        "status_pengumpulan": status.get("Status pengumpulan", "-"),
        "status_penilaian": status.get("Status penilaian", "-"),
        "batas_waktu": status.get("Batas waktu", "-"),
        "waktu_tersisa": status.get("Waktu tersisa", "-"),
        "pemutahiran_terakhir": status.get("Pemutahiran terakhir", "-"),
        "ringkasan_soal": ringkasan_soal,
        "instruksi_penuh": instruksi_penuuh,
        "belum_dikumpulkan": belum_dikumpulkan,
    }


def format_blok_tugas(indeks, timeline, detail):
    nama = detail.get("judul") or timeline["nama"]
    status_kumpul = detail.get("status_pengumpulan", "-")
    emoji_status = "🔴" if detail.get("belum_dikumpulkan") else "🟢"

    blok = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>TUGAS #{indeks}</b>\n\n"
        f"🔹 <b>Judul:</b> {escape_html(nama)}\n"
        f"📚 <b>Mata Kuliah:</b> {escape_html(timeline['mata_kuliah'])}\n"
        f"📂 <b>Jenis Aktivitas:</b> {escape_html(timeline['jenis_aktivitas'])}\n\n"
        f"⏰ <b>Tenggat:</b> {escape_html(detail.get('batas_waktu') or timeline['tenggat_penuh'] or '-')}\n"
        f"🕐 <b>Jam Tenggat:</b> {escape_html(timeline['jam_tenggat'] or '-')}\n"
        f"⌛ <b>Sisa Waktu:</b> {escape_html(detail.get('waktu_tersisa', '-'))}\n\n"
        f"{emoji_status} <b>Status Pengumpulan:</b> {escape_html(status_kumpul)}\n"
        f"📊 <b>Status Penilaian:</b> {escape_html(detail.get('status_penilaian', '-'))}\n"
        f"🔄 <b>Pemutahiran Terakhir:</b> {escape_html(detail.get('pemutahiran_terakhir', '-'))}\n"
    )

    if detail.get("ringkasan_soal"):
        blok += f"\n📝 <b>Ringkasan Instruksi:</b>\n<i>{escape_html(detail['ringkasan_soal'])}</i>\n"

    blok += f"\n🔗 *Link Tugas:*\n{timeline['link_tugas']}\n"
    if timeline.get("link_submit"):
        blok += f"📤 *Link Pengumpulan:*\n{timeline['link_submit']}\n"

    return blok


# --- 3. FUNGSI LLM AI ---
def _daftar_model_llm():
    utama = LLM_MODEL
    custom = _env("LLM_FALLBACK_MODELS", "")
    cadangan = (
        [m.strip() for m in custom.split(",") if m.strip()]
        if custom
        else (OPENROUTER_FALLBACK_MODELS if LLM_PROVIDER == "openrouter" else [])
    )
    urutan, seen = [], set()
    for model in [utama] + cadangan:
        if model and model not in seen:
            seen.add(model)
            urutan.append(model)
    return urutan


def _is_rate_limit_error(err):
    teks = str(err).lower()
    return "429" in teks or "rate" in teks or "rate-limited" in teks


def _panggil_llm(model, messages):
    for percobaan in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=4096,
            )
            return response.choices[0].message.content, None
        except Exception as e:
            if _is_rate_limit_error(e) and percobaan < 2:
                tunggu = 25 * (percobaan + 1)
                print(f"[AI] Rate limit pada {model}, tunggu {tunggu}s lalu coba lagi...")
                time.sleep(tunggu)
                continue
            return None, e
    return None, None


def minta_jawaban_hermes(soal_tugas):
    global LAST_LLM_MODEL_USED

    if not LLM_API_KEY:
        return "API key belum diatur di file .env"

    system_prompt = (
        "Kamu adalah asisten akademik universitas tingkat tinggi. "
        "Tugasmu adalah menyelesaikan tugas kuliah yang diberikan oleh user. "
        "Berikan jawaban yang sangat mendalam, analitis, terstruktur dengan baik, "
        "dan gunakan bahasa Indonesia yang natural, cerdas, layaknya mahasiswa asli. "
        "HINDARI gaya bahasa kaku khas AI seperti 'Dalam era digital ini' atau 'Signifikan'."
    )
    if len(soal_tugas) > 12000:
        soal_tugas = soal_tugas[:12000] + "\n\n[...teks dipotong...]"
    user_prompt = f"Selesaikan tugas kuliah ini dengan kualitas terbaik:\n\n{soal_tugas}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    model_list = _daftar_model_llm()
    for model in model_list:
        print(f"[AI] Mencoba model: {model}")
        jawaban, err = _panggil_llm(model, messages)
        if jawaban:
            LAST_LLM_MODEL_USED = model
            return jawaban
        print(f"[AI Error] {model}: {err}")

    return "Semua model AI sibuk atau kuota habis. Silakan coba lagi nanti."


def login_elearning(page):
    page.goto(f"{ELEARNING_URL}/login/index.php", timeout=60000)
    page.wait_for_selector("#username", state="visible")
    page.locator("#username").fill(ELEARNING_USERNAME)
    page.locator("#password").fill(ELEARNING_PASSWORD)

    with page.expect_navigation(timeout=30000):
        page.locator("#loginbtn").click()

    if page.locator(".loginerrors, #loginerrormessage").count() > 0 or "/login/index.php" in page.url:
        return False
    return True


# --- TAHAP BARU: PENYIMPANAN DATA UTK PERMINTAAN MANUAL ---
# Penyimpanan sementara dalam memori RAM agar file teks soal bisa diambil kapan saja lewat Telegram
MEMORI_TUGAS = {}

# --- 4. CORE AGENT EXECUTION ---
def run_hermes_agent():
    print("\n====================================")
    print("Running Hermes Agent (Mode Manual AI)...")
    print("====================================")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("[Playwright] Menuju halaman login...")
            if not login_elearning(page):
                print("[Login Gagal] Gagal login ke E-Learning.")
                send_telegram_message("⚠️ <b>PERINGATAN:</b> Hermes gagal login E-Learning.")
                return

            print("[Playwright] Login sukses. Membuka dasbor...")
            page.goto(f"{ELEARNING_URL}/my/", timeout=60000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            print("[Playwright] Membaca blok Linimasa...")
            timeline_items = page.locator("[data-region='event-list-item'], .event-list-item, .timeline-event-item")
            total_tugas = timeline_items.count()
            print(f"[Status] Ditemukan total {total_tugas} tugas aktif.")

            if total_tugas > 0:
                waktu_cek = datetime.now().strftime("%d %B %Y, %H:%M")
                
                # Pemrosesan satu per satu tugas
                for i in range(total_tugas):
                    try:
                        item = timeline_items.nth(i)
                        timeline = parse_timeline_item(item)
                        if not timeline["link_tugas"]:
                            continue

                        print(f"[Playwright] Mengambil rincian: {timeline['nama']}")
                        detail = ambil_detail_tugas(page, timeline["link_tugas"])
                        
                        # Bangun pesan laporan per item tugas
                        pesan_item = (
                            "📋 <b>HERMES REPORT: DETAIL TUGAS</b>\n"
                            f"🕐 <b>Pengecekan:</b> {escape_html(waktu_cek)}\n"
                        )
                        pesan_item += format_blok_tugas(i + 1, timeline, detail)
                        
                        reply_markup = None
                        # JIKA BELUM DIKUMPULKAN, BUAT TOMBOL MINTA JAWABAN AI
                        if detail.get("belum_dikumpulkan"):
                            # Bersihkan ID unik dari link Moodle untuk penanda tombol callback
                            match_id = re.search(r"id=(\d+)", timeline["link_tugas"])
                            id_tugas = match_id.group(1) if match_id else str(i)
                            
                            # Simpan dokumen soal ke memori RAM global
                            MEMORI_TUGAS[id_tugas] = {
                                "nama": detail.get("judul") or timeline["nama"],
                                "link": timeline["link_tugas"],
                                "soal": detail.get("instruksi_penuh")
                            }

                            # Pasang struktur data tombol inline telegram
                            reply_markup = {
                                "inline_keyboard": [[
                                    {"text": "🤖 Minta Jawaban AI", "callback_data": f"jawab_{id_tugas}"}
                                ]]
                            }
                            pesan_item += "\n💡 <i>Klik tombol di bawah ini jika kamu ingin draf jawaban AI dibuat.</i>"
                        
                        # Kirim detail tugas ke Telegram saat itu juga
                        send_telegram_message(pesan_item, reply_markup=reply_markup)
                        
                    except Exception as e_item:
                        print(f"[Warning] Gagal membaca baris linimasa ke-{i}: {e_item}")

            else:
                print("[Status] Bersih! Tidak ada tugas aktif di Linimasa.")

        except PlaywrightTimeoutError as te:
            print(f"[Timeout Error] Koneksi lambat: {te}")
        except Exception as e:
            print(f"[Unexpected Error] Kendala: {e}")
        finally:
            try:
                browser.close()
                print("[Playwright] Sesi browser ditutup.")
            except Exception as e_close:
                print(f"[Playwright Warning] Browser putus duluan: {e_close}")


# --- 5. SERVER BOT TELEGRAM (UNTUK MENDENGARKAN KLIK TOMBOL) ---
def jalankan_polling_tombol():
    """Fungsi yang berjalan di background untuk merespons klik tombol kamu."""
    offset = None
    url_updates = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    print("[Telegram Bot] Polling tombol manual aktif...")
    while True:
        try:
            params = {"timeout": 10, "offset": offset}
            res = requests.get(url_updates, params=params, timeout=15).json()
            
            if "result" in res:
                for update in res["result"]:
                    offset = update["update_id"] + 1
                    
                    # --- HANDLE PESAN TEKS BIASA ---
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg.get("chat", {}).get("id")
                        text = msg.get("text", "").strip()
                        # Abaikan pesan tanpa teks (foto, stiker, dll)
                        if text:
                            print(f"[Bot] Pesan diterima: '{text}' dari chat {chat_id}")
                            perintah = text.lower().split()[0] if text else ""
                            # Balas sapaan
                            if text.lower() in ("hallo hermes", "halo hermes", "hello hermes", "hi hermes"):
                                send_telegram_message("Halo! Saya Hermes, asisten e-learning kamu. Ketik /cektugas untuk melihat tugas aktif.", chat_id=chat_id)
                            # Perintah cek tugas manual
                            elif perintah == "/cektugas":
                                send_telegram_message("⏳ Memeriksa tugas e-learning, mohon tunggu...", chat_id=chat_id)
                                try:
                                    run_hermes_agent()
                                except Exception as e:
                                    send_telegram_message(f"❌ Gagal cek tugas: {escape_html(str(e))}", chat_id=chat_id)
                            else:
                                send_telegram_message("Saya hanya merespon:\n• <b>hallo hermes</b> — sapaan\n• <b>/cektugas</b> — cek tugas aktif", chat_id=chat_id)

                    # --- HANDLE KLIK TOMBOL (callback_query) ---
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        data_klik = cb["data"] # contoh: "jawab_12345"
                        
                        # Kirim sinyal loading (loading animation di tombol)
                        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery", 
                                      json={"callback_query_id": cb_id, "text": "Hermes sedang berfikir... 🧠"})
                        
                        if data_klik.startswith("jawab_"):
                            id_tugas = data_klik.split("_")[1]
                            
                            if id_tugas in MEMORI_TUGAS:
                                data_t = MEMORI_TUGAS[id_tugas]
                                
                                send_telegram_message(f"⏳ <b>Memulai Analisis AI untuk:</b> {escape_html(data_t['nama'])}...")
                                
                                # Panggil LLM secara langsung saat diminta
                                jawaban = minta_jawaban_hermes(data_t["soal"])
                                kirim_analisis_jawaban(data_t["nama"], data_t["link"], jawaban)
                            else:
                                send_telegram_message("❌ Data soal tugas ini sudah kedaluwarsa di memori RAM bot. Tunggu jadwal pengecekan berikutnya.")
                                
        except Exception as e:
            print(f"[Telegram Polling Error] {e}")
        time.sleep(1)


# --- 6. MAIN MULTI-THREADING EXECUTION ---
if __name__ == "__main__":
    import threading
    print("Hermes Agent System Started.")
    
    # Jalankan pendengar klik tombol telegram di Thread terpisah agar berjalan beriringan
    thread_tombol = threading.Thread(target=jalankan_polling_tombol, daemon=True)
    thread_tombol.start()
    
    # Loop Pengecekan Utama E-Learning 2 Jam Sekali
    while True:
        try:
            run_hermes_agent()
        except Exception as e:
            print(f"[Loop Global Error] Terjadi kegagalan: {e}")
            
        print("Menunggu 2 jam untuk pengecekan berikutnya...")
        time.sleep(7200)