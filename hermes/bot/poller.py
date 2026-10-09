"""Proses bot: long-poll Telegram, tangani perintah dan klik tombol.

Pengecekan E-Learning dijalankan sebagai subprocess supaya polling tidak
tersendat menunggu Playwright selesai.

Jalankan:
    python -m hermes.bot.poller
"""

import os
import subprocess
import sys
import time

import requests

from ..common import store
from ..common.config import TELEGRAM_BOT_TOKEN
from ..common.report import teks_agent, teks_kelas
from ..common.telegram import escape_html, send_telegram_message
from ..roster import cari_agent
from .menu import BANTUAN, teks_selamat_datang

SAPAAN = ("hallo hermes", "halo hermes", "hello hermes", "hi hermes")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def jalankan_cek_tugas(chat_id):
    """Jalankan scraper sekali sebagai proses terpisah."""
    try:
        subprocess.Popen(
            [sys.executable, "-m", "hermes.scraper.run_check", "--once"],
            cwd=BASE_DIR,
        )
        send_telegram_message(
            "⏳ Memeriksa tugas e-learning, hasilnya dikirim setelah selesai...",
            chat_id=chat_id,
        )
    except Exception as e:
        send_telegram_message(f"❌ Gagal menjalankan pengecekan: {escape_html(str(e))}", chat_id=chat_id)


def tangani_pesan(msg):
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    if not text:
        return

    perintah = text.lower().split()[0]
    print(f"[Bot] Pesan diterima: '{text}' dari chat {chat_id}")

    if text.lower() in SAPAAN:
        send_telegram_message(teks_selamat_datang(), chat_id=chat_id)

    elif perintah == "/start":
        send_telegram_message(teks_selamat_datang(), chat_id=chat_id)

    elif perintah == "/help":
        send_telegram_message(BANTUAN, chat_id=chat_id)

    elif perintah == "/kelas":
        send_telegram_message(teks_kelas(), chat_id=chat_id)

    elif perintah == "/agent":
        bagian = text.split(maxsplit=1)
        if len(bagian) < 2:
            send_telegram_message(
                "❌ Format: <code>/agent [mata kuliah]</code>\nContoh: /agent kecerdasan buatan",
                chat_id=chat_id,
            )
            return
        send_telegram_message(teks_agent(bagian[1]), chat_id=chat_id)

    elif perintah == "/cektugas":
        jalankan_cek_tugas(chat_id)

    else:
        send_telegram_message(BANTUAN, chat_id=chat_id)


def tangani_tombol(cb):
    cb_id = cb["id"]
    data_klik = cb.get("data") or ""
    chat_id = cb.get("message", {}).get("chat", {}).get("id")

    if not data_klik.startswith("jawab_"):
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cb_id, "text": "Perintah tidak dikenal."},
        )
        return

    id_tugas = data_klik.split("_", 1)[1]
    tugas = store.ambil_tugas(id_tugas)

    if not tugas:
        pesan = "❌ Data tugas ini belum ada di database. Jalankan /cektugas dulu."
        dikirim = False
    elif store.antri_jawaban(id_tugas):
        pesan = f"🧠 {tugas.get('nama')} sudah masuk antrian. Draf dikirim setelah selesai."
        dikirim = True
    else:
        pesan = "⏳ Tugas ini sudah ada di antrian atau sedang diproses."
        dikirim = False

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
        json={"callback_query_id": cb_id, "text": pesan[:200]},
    )
    if dikirim:
        send_telegram_message(
            f"🧠 <b>{escape_html(cari_agent(tugas.get('mata_kuliah'))['nama'])}</b> mulai mengerjakan:\n"
            f"{escape_html(tugas.get('nama'))}\n\n<i>Draf dikirim otomatis setelah selesai.</i>",
            chat_id=chat_id,
        )


def main():
    store.init_db()
    offset = None
    url_updates = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    print("[Bot] Polling perintah dan tombol aktif...")

    while True:
        try:
            res = requests.get(
                url_updates, params={"timeout": 10, "offset": offset}, timeout=15
            ).json()

            for update in res.get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    tangani_pesan(update["message"])
                if "callback_query" in update:
                    tangani_tombol(update["callback_query"])

        except Exception as e:
            print(f"[Bot Polling Error] {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
