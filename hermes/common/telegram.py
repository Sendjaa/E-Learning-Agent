"""Helper pengiriman pesan Telegram (HTML) dan pemecahan pesan panjang."""

import requests

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_MAX_LEN = 4096


def escape_html(text):
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


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


def kirim_analisis_jawaban(nama_tugas, link_tugas, jawaban, model=""):
    """Kirim draf jawaban AI, dipecah agar tidak menembus batas pesan Telegram."""
    if not jawaban or not jawaban.strip():
        jawaban = "(Model tidak mengembalikan jawaban.)"

    header = (
        "🚨 <b>ANALISIS JAWABAN TUGAS</b>\n\n"
        f"📌 <b>Tugas:</b> {escape_html(nama_tugas)}\n"
        f"🔗 <b>Link:</b> {link_tugas}\n"
        f"🤖 <b>Model:</b> {escape_html(model or '-')}"
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


def kirim_ulasan_pm(nama_pm, nama_tugas, seat, link_tugas, ulasan, model=""):
    """Kirim hasil pemeriksaan PM atas draf salah satu kursi."""
    if not ulasan or not ulasan.strip():
        ulasan = "(Model tidak mengembalikan hasil pemeriksaan.)"

    header = (
        "🔍 <b>PEMERIKSAAN PM</b>\n\n"
        f"👤 <b>Pemeriksa:</b> {escape_html(nama_pm)}\n"
        f"🧩 <b>Diperiksa:</b> {escape_html(seat)}\n"
        f"📌 <b>Tugas:</b> {escape_html(nama_tugas)}\n"
        f"🔗 <b>Link:</b> {link_tugas}\n"
        f"🤖 <b>Model:</b> {escape_html(model or '-')}"
    )
    if not send_telegram_message(header):
        return False

    potongan = _pecah_pesan(ulasan.strip(), 3500)
    total = len(potongan)
    for i, bagian in enumerate(potongan, start=1):
        label = "📋 <b>HASIL PEMERIKSAAN:</b>"
        if total > 1:
            label += f" <i>(bagian {i}/{total})</i>"
        if not send_telegram_message(f"{label}\n<pre>{escape_html(bagian)}</pre>"):
            return False

    return send_telegram_message(
        "<i>PM belum mengubah apa pun. Perbaikan tetap keputusanmu.</i>"
    )
