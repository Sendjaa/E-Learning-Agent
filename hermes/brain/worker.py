"""Proses brain: ambil permintaan jawaban dari antrian, buat draf, kirim ke Telegram.

Jalankan:
    python -m hermes.brain.worker            # loop, jeda WORKER_INTERVAL
    python -m hermes.brain.worker --once     # proses satu permintaan lalu keluar
"""

import sys
import time

from ..common import store
from ..common.config import PM_REVIEW, WORKER_INTERVAL
from ..common.llm import minta_jawaban
from ..common.telegram import (
    escape_html,
    kirim_analisis_jawaban,
    kirim_ulasan_pm,
    send_telegram_message,
)
from ..roster import agent_pm, cari_agent


def periksa_oleh_pm(tugas, id_moodle, seat, jawaban):
    """Kursi PM memeriksa draf kursi lain. Menghabiskan satu panggilan LLM lagi."""
    pm = agent_pm()
    if not pm or pm["nama"] == seat["nama"]:
        return

    soal = (
        f"Periksa hasil kerja kursi {seat['nama']} untuk tugas berikut.\n\n"
        f"JUDUL TUGAS: {tugas.get('nama')}\n\n"
        f"INSTRUKSI ASLI:\n{tugas.get('instruksi_penuh') or tugas.get('ringkasan') or '-'}\n\n"
        f"HASIL KERJA YANG DIPERIKSA:\n{jawaban}\n\n"
        "Nilai: apakah sudah menjawab instruksi, apa yang kurang atau salah, dan apa "
        "yang perlu diperbaiki. Tutup dengan keputusan LOLOS atau PERLU REVISI."
    )

    try:
        ulasan, model = minta_jawaban(soal, system_prompt=pm["prompt"])
    except Exception as e:
        print(f"[Brain] Pemeriksaan PM gagal untuk {id_moodle}: {e}")
        send_telegram_message(f"⚠️ PM gagal memeriksa '{escape_html(tugas.get('nama'))}':\n<code>{e}</code>")
        return

    store.simpan_ulasan(id_moodle, pm["nama"], model, ulasan)
    kirim_ulasan_pm(
        pm["nama"],
        tugas.get("nama") or "-",
        seat["nama"],
        tugas.get("link") or "-",
        ulasan,
        model=model,
    )


def proses_permintaan(permintaan):
    id_moodle = permintaan["id_moodle"]
    tugas = store.ambil_tugas(id_moodle)

    if not tugas:
        store.tandai_permintaan(permintaan["id"], "gagal")
        print(f"[Brain] Tugas {id_moodle} tidak ada di database.")
        return False

    soal = tugas.get("instruksi_penuh") or tugas.get("ringkasan") or ""
    if not soal.strip():
        store.tandai_permintaan(permintaan["id"], "gagal")
        send_telegram_message(
            f"❌ Tidak ada teks soal tersimpan untuk tugas <b>{tugas.get('nama')}</b>.\n"
            "Coba jalankan /cektugas dulu supaya instruksinya terambil ulang."
        )
        return False

    agent = cari_agent(tugas.get("mata_kuliah"))
    store.tandai_permintaan(permintaan["id"], "proses")
    print(f"[Brain] {agent['nama']} mengerjakan: {tugas.get('nama')}")

    jawaban, model = minta_jawaban(soal, system_prompt=agent["prompt"])

    store.simpan_jawaban(id_moodle, model, jawaban)
    store.tandai_permintaan(permintaan["id"], "selesai")

    kirim_analisis_jawaban(
        f"[{agent['nama']}] {tugas.get('nama')}",
        tugas.get("link") or "-",
        jawaban,
        model=model,
    )

    if PM_REVIEW:
        periksa_oleh_pm(tugas, id_moodle, agent, jawaban)
    return True


def main():
    store.init_db()
    sekali = "--once" in sys.argv
    print("[Brain] Worker antrian jawaban aktif...")

    while True:
        permintaan = store.ambil_permintaan_pending()
        if permintaan:
            try:
                proses_permintaan(permintaan)
            except Exception as e:
                store.tandai_permintaan(permintaan["id"], "gagal")
                print(f"[Brain Error] {e}")
                send_telegram_message(f"❌ Gagal membuat draf jawaban:\n<code>{e}</code>")
            if sekali:
                return
            continue

        if sekali:
            print("[Brain] Tidak ada permintaan pending.")
            return
        time.sleep(WORKER_INTERVAL)


if __name__ == "__main__":
    main()
