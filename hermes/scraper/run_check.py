"""Proses scraper: cek linimasa Moodle, simpan tugas ke DB, lapor ke Telegram.

Jalankan:
    python -m hermes.scraper.run_check            # loop, jeda CHECK_INTERVAL
    python -m hermes.scraper.run_check --once     # sekali jalan lalu keluar
"""

import os
import sys
import time
from datetime import datetime

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from ..common import store
from ..common.config import CHECK_INTERVAL, ELEARNING_URL
from ..common.report import teks_kelas
from ..common.telegram import escape_html, send_telegram_message
from .moodle import (
    SELECTOR_ITEM_LINIMASA,
    ambil_detail_tugas,
    format_blok_tugas,
    id_tugas_dari_link,
    login_elearning,
    parse_timeline_item,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def kirim_ringkasan_kelas():
    """Simpan snapshot beban lalu kirim papan kelas ke Telegram."""
    store.simpan_snapshot_beban()
    send_telegram_message(
        f"{teks_kelas()}\n🕐 Snapshot beban tersimpan: {datetime.now():%d %B %Y, %H:%M}"
    )


def jalankan_pengecekan():
    print("\n====================================")
    print("Running Hermes Scraper (mode manual AI)...")
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
            # Blok Linimasa diisi lewat AJAX setelah DOM siap: tunggu elemennya,
            # jangan asal sleep -- 3 detik sering belum cukup di koneksi lambat.
            try:
                page.wait_for_selector(SELECTOR_ITEM_LINIMASA, timeout=30000)
            except PlaywrightTimeoutError:
                print("[Playwright] Elemen linimasa tak muncul dalam 30s.")
            time.sleep(1)

            print("[Playwright] Membaca blok Linimasa...")
            timeline_items = page.locator(SELECTOR_ITEM_LINIMASA)
            total_tugas = timeline_items.count()
            print(f"[Status] Ditemukan total {total_tugas} tugas aktif.")

            if total_tugas > 0:
                waktu_cek = datetime.now().strftime("%d %B %Y, %H:%M")

                # Parse SEMUA baris linimasa dulu. ambil_detail_tugas() memakai
                # page.goto(), jadi locator linimasa sudah hilang begitu tugas
                # pertama dibuka -- kalau di-parse sambil jalan, tugas ke-2 dst gagal.
                baris_linimasa = []
                for i in range(total_tugas):
                    try:
                        baris_linimasa.append(parse_timeline_item(timeline_items.nth(i)))
                    except Exception as e_item:
                        print(f"[Warning] Gagal membaca baris linimasa ke-{i}: {e_item}")

                for i, timeline in enumerate(baris_linimasa):
                    try:
                        if not timeline["link_tugas"]:
                            continue

                        print(f"[Playwright] Mengambil rincian: {timeline['nama']}")
                        detail = ambil_detail_tugas(page, timeline["link_tugas"])
                        id_tugas = id_tugas_dari_link(timeline["link_tugas"], i)

                        # Simpan ke DB supaya tidak hilang saat proses restart
                        store.simpan_tugas({
                            "id_moodle": id_tugas,
                            "nama": detail.get("judul") or timeline["nama"],
                            "mata_kuliah": timeline["mata_kuliah"],
                            "tenggat": detail.get("batas_waktu") or timeline["tenggat_penuh"],
                            "status_kumpul": detail.get("status_pengumpulan", "-"),
                            "ringkasan": detail.get("ringkasan_soal", ""),
                            "instruksi_penuh": detail.get("instruksi_penuh", ""),
                            "link": timeline["link_tugas"],
                            "link_submit": timeline.get("link_submit", ""),
                        })

                        pesan_item = (
                            "📋 <b>HERMES REPORT: DETAIL TUGAS</b>\n"
                            f"🕐 <b>Pengecekan:</b> {escape_html(waktu_cek)}\n"
                        )
                        pesan_item += format_blok_tugas(i + 1, timeline, detail)

                        reply_markup = None
                        if detail.get("belum_dikumpulkan"):
                            # Hanya tawarkan -- jawaban dibuat saat tombol diklik,
                            # supaya kuota LLM gratis tidak terbakar untuk semua tugas.
                            reply_markup = {
                                "inline_keyboard": [[
                                    {"text": "🤖 Minta Jawaban AI", "callback_data": f"jawab_{id_tugas}"}
                                ]]
                            }
                            pesan_item += (
                                "\n💡 <i>Klik tombol di bawah ini jika kamu ingin draf jawaban AI dibuat.</i>"
                            )

                        send_telegram_message(pesan_item, reply_markup=reply_markup)

                    except Exception as e_item:
                        print(f"[Warning] Gagal memproses tugas ke-{i}: {e_item}")

                kirim_ringkasan_kelas()

            else:
                print("[Status] Bersih! Tidak ada tugas aktif di Linimasa.")
                jumlah_blok = page.locator(".block_timeline").count()
                jumlah_region = page.locator("[data-region^='event-list']").count()
                jumlah_link_assign = page.locator("a[href*='mod/assign']").count()
                print(
                    f"[Debug] blok_timeline={jumlah_blok} "
                    f"region_event_list={jumlah_region} link_mod_assign={jumlah_link_assign}"
                )
                dump = os.path.join(BASE_DIR, "debug_linimasa.html")
                try:
                    with open(dump, "w", encoding="utf-8") as f_dump:
                        f_dump.write(page.content())
                except OSError as e_dump:
                    print(f"[Debug] Gagal tulis dump: {e_dump}")
                send_telegram_message(
                    "✅ <b>Tidak ada tugas aktif</b> di Linimasa E-Learning saat ini.\n"
                    f"🌐 URL: {escape_html(page.url)}\n"
                    f"🧩 blok_timeline: {jumlah_blok} | region_event_list: {jumlah_region} | "
                    f"link mod/assign: {jumlah_link_assign}\n"
                    f"<i>HTML halaman disimpan ke {escape_html(dump)} untuk diperiksa.</i>"
                )

        except PlaywrightTimeoutError as te:
            print(f"[Timeout Error] Koneksi lambat: {te}")
            send_telegram_message(
                "⏱️ <b>Timeout saat membuka E-Learning.</b>\n"
                "Cek koneksi lalu jalankan /cektugas lagi.\n"
                f"<code>{escape_html(str(te))}</code>"
            )
        except Exception as e:
            print(f"[Unexpected Error] Kendala: {e}")
            send_telegram_message(
                "❌ <b>Gagal cek tugas:</b>\n"
                f"<code>{escape_html(str(e))}</code>"
            )
        finally:
            try:
                browser.close()
                print("[Playwright] Sesi browser ditutup.")
            except Exception as e_close:
                print(f"[Playwright Warning] Browser putus duluan: {e_close}")


def main():
    store.init_db()
    sekali = "--once" in sys.argv

    while True:
        try:
            jalankan_pengecekan()
        except Exception as e:
            print(f"[Loop Global Error] Terjadi kegagalan: {e}")

        if sekali:
            return
        print(f"Menunggu {CHECK_INTERVAL // 3600} jam untuk pengecekan berikutnya...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
