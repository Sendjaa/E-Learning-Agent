"""Scraping linimasa dan detail tugas Moodle lewat Playwright."""

import re

from ..common.config import ELEARNING_PASSWORD, ELEARNING_URL, ELEARNING_USERNAME
from ..common.telegram import escape_html

# Selector blok Linimasa Moodle (core: li[data-region='event-list-item'])
SELECTOR_ITEM_LINIMASA = (
    "[data-region='event-list-item'], .event-list-item, .timeline-event-item"
)


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
    instruksi_penuh = page.locator("#region-main").inner_text()

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
        "instruksi_penuh": instruksi_penuh,
        "belum_dikumpulkan": belum_dikumpulkan,
    }


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

    blok += f"\n🔗 <b>Link Tugas:</b>\n{timeline['link_tugas']}\n"
    if timeline.get("link_submit"):
        blok += f"📤 <b>Link Pengumpulan:</b>\n{timeline['link_submit']}\n"

    return blok


def id_tugas_dari_link(link, fallback):
    """Ambil id numerik dari link Moodle untuk penanda callback tombol."""
    match = re.search(r"id=(\d+)", link or "")
    return match.group(1) if match else str(fallback)
