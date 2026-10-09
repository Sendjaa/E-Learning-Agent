"""SQLite sebagai tulang punggung: simpan tugas, antrian jawaban, dan snapshot beban.

Dipakai bersama oleh empat proses (scraper, brain, bot, dashboard), jadi setiap
koneksi wajib WAL + busy_timeout — tanpa itu proses-proses ini saling mengunci.
"""

import os
import sqlite3
from datetime import datetime, timedelta

from .config import (
    DB_PATH,
    SOON_HOURS,
    URGENT_HOURS,
    WEIGHT_NORMAL,
    WEIGHT_SOON,
    WEIGHT_URGENT,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tugas (
    id_moodle       TEXT PRIMARY KEY,
    nama            TEXT,
    mata_kuliah     TEXT,
    tenggat         TEXT,
    tenggat_dt      TEXT,
    status_kumpul   TEXT,
    ringkasan       TEXT,
    instruksi_penuh TEXT,
    link            TEXT,
    link_submit     TEXT,
    terakhir_dilihat TEXT
);

CREATE TABLE IF NOT EXISTS beban (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    waktu           TEXT,
    agent           TEXT,
    jumlah_tugas    INTEGER,
    jumlah_mendesak INTEGER,
    skor            INTEGER
);

CREATE TABLE IF NOT EXISTS permintaan_jawaban (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_moodle   TEXT UNIQUE,
    status      TEXT,
    dibuat      TEXT,
    diproses    TEXT
);

CREATE TABLE IF NOT EXISTS jawaban (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_moodle   TEXT,
    model       TEXT,
    isi         TEXT,
    waktu       TEXT
);

CREATE TABLE IF NOT EXISTS ulasan (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_moodle   TEXT,
    penulis     TEXT,
    model       TEXT,
    isi         TEXT,
    waktu       TEXT
);
"""

# Moodle memakai nama bulan Indonesia; tanpa ini tenggat tidak bisa dihitung.
BULAN_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "agu": 8, "agt": 8,
    "sep": 9, "okt": 10, "nov": 11, "des": 12,
}


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ==================== PARSING TENGGAT ====================

HARI_ID = ("senin", "selasa", "rabu", "kamis", "jumat", "jum'at", "sabtu", "minggu", "ahad")


def parse_tenggat(teks):
    """Ubah teks tenggat Moodle jadi datetime. Kembalikan None jika tak dikenali.

    Contoh yang ditangani: 'Selasa, 14 Oktober 2026, 23.59' dan '14 Okt 2026, 11:30 PM'.
    Kalau format kampus berubah, tambahkan polanya di sini.
    """
    if not teks:
        return None

    bersih = " ".join(str(teks).replace(".", ":").split())
    bagian = [b.strip() for b in bersih.split(",") if b.strip()]

    # buang nama hari di depan
    if bagian and bagian[0].split()[0].lower() in HARI_ID:
        bagian = bagian[1:]
    if not bagian:
        return None

    tanggal = bagian[0].split()
    if len(tanggal) < 3:
        return None

    bulan = BULAN_ID.get(tanggal[1].lower())
    if not bulan:
        return None

    try:
        hari, tahun = int(tanggal[0]), int(tanggal[2])
    except ValueError:
        return None

    jam, menit = 0, 0
    if len(bagian) >= 2:
        pukul = bagian[1].split()
        try:
            angka = [int(x) for x in pukul[0].split(":")]
        except (ValueError, IndexError):
            angka = [0]
        jam = angka[0]
        menit = angka[1] if len(angka) > 1 else 0
        # '11:30 PM' -> 23:30
        if len(pukul) >= 2 and pukul[1].lower() == "pm" and 0 < jam < 12:
            jam += 12

    try:
        return datetime(hari, bulan, tahun, jam, menit)
    except ValueError:
        return None


def bobot_urgensi(sisa_jam):
    """Bobot beban sebuah tugas berdasarkan sisa waktu (jam). None = tak diketahui."""
    if sisa_jam is None:
        return WEIGHT_NORMAL
    if sisa_jam < URGENT_HOURS:
        return WEIGHT_URGENT
    if sisa_jam < SOON_HOURS:
        return WEIGHT_SOON
    return WEIGHT_NORMAL


def skor_beban(sisa_jam_list):
    """Total skor beban dari daftar sisa waktu (jam) tiap tugas."""
    return sum(bobot_urgensi(s) for s in sisa_jam_list)


# ==================== TUGAS ====================

def simpan_tugas(tugas):
    """Simpan/perbarui satu tugas. `tugas` = dict dengan kunci sesuai kolom."""
    dt = parse_tenggat(tugas.get("tenggat"))
    conn = connect()
    try:
        conn.execute(
            """
            INSERT INTO tugas (id_moodle, nama, mata_kuliah, tenggat, tenggat_dt,
                               status_kumpul, ringkasan, instruksi_penuh, link,
                               link_submit, terakhir_dilihat)
            VALUES (:id_moodle, :nama, :mata_kuliah, :tenggat, :tenggat_dt,
                    :status_kumpul, :ringkasan, :instruksi_penuh, :link,
                    :link_submit, :terakhir_dilihat)
            ON CONFLICT(id_moodle) DO UPDATE SET
                nama=excluded.nama,
                mata_kuliah=excluded.mata_kuliah,
                tenggat=excluded.tenggat,
                tenggat_dt=excluded.tenggat_dt,
                status_kumpul=excluded.status_kumpul,
                ringkasan=excluded.ringkasan,
                instruksi_penuh=excluded.instruksi_penuh,
                link=excluded.link,
                link_submit=excluded.link_submit,
                terakhir_dilihat=excluded.terakhir_dilihat
            """,
            {
                "id_moodle": str(tugas.get("id_moodle")),
                "nama": tugas.get("nama") or "",
                "mata_kuliah": tugas.get("mata_kuliah") or "",
                "tenggat": tugas.get("tenggat") or "",
                "tenggat_dt": dt.isoformat() if dt else None,
                "status_kumpul": tugas.get("status_kumpul") or "-",
                "ringkasan": tugas.get("ringkasan") or "",
                "instruksi_penuh": tugas.get("instruksi_penuh") or "",
                "link": tugas.get("link") or "",
                "link_submit": tugas.get("link_submit") or "",
                "terakhir_dilihat": datetime.now().isoformat(timespec="seconds"),
            },
        )
        conn.commit()
    finally:
        conn.close()


def ambil_tugas(id_moodle):
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM tugas WHERE id_moodle = ?", (str(id_moodle),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def semua_tugas():
    conn = connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM tugas ORDER BY tenggat_dt").fetchall()]
    finally:
        conn.close()


def sisa_jam(tugas, sekarang=None):
    """Sisa waktu tugas dalam jam, atau None kalau tenggat tak bisa dibaca."""
    if not tugas.get("tenggat_dt"):
        return None
    try:
        dt = datetime.fromisoformat(tugas["tenggat_dt"])
    except ValueError:
        return None
    return (dt - (sekarang or datetime.now())).total_seconds() / 3600


def tugas_belum_dikumpul():
    return [t for t in semua_tugas() if "belum" in (t.get("status_kumpul") or "").lower()]


# ==================== BEBAN ====================

def hitung_beban(sekarang=None):
    """Skor beban per mata kuliah, dihitung dari tugas yang belum dikumpulkan."""
    hasil = {}
    for t in tugas_belum_dikumpul():
        mk = t.get("mata_kuliah") or "Tanpa Mata Kuliah"
        jam = sisa_jam(t, sekarang)
        entri = hasil.setdefault(mk, {"jumlah": 0, "mendesak": 0, "skor": 0})
        entri["jumlah"] += 1
        entri["skor"] += bobot_urgensi(jam)
        if jam is not None and jam < URGENT_HOURS:
            entri["mendesak"] += 1
    return hasil


def simpan_snapshot_beban():
    beban = hitung_beban()
    conn = connect()
    try:
        waktu = datetime.now().isoformat(timespec="seconds")
        conn.executemany(
            "INSERT INTO beban (waktu, agent, jumlah_tugas, jumlah_mendesak, skor) VALUES (?, ?, ?, ?, ?)",
            [(waktu, mk, v["jumlah"], v["mendesak"], v["skor"]) for mk, v in beban.items()],
        )
        conn.commit()
    finally:
        conn.close()
    return beban


def terakhir_cek():
    conn = connect()
    try:
        row = conn.execute("SELECT MAX(terakhir_dilihat) AS t FROM tugas").fetchone()
        return row["t"] if row else None
    finally:
        conn.close()


# ==================== ANTRIAN JAWABAN ====================

def antri_jawaban(id_moodle):
    """Antrikan permintaan jawaban untuk satu tugas.

    Kembalikan False kalau tugas ini sudah diantrikan atau sedang diproses.
    Permintaan yang sudah selesai/gagal boleh diulang.
    """
    id_moodle = str(id_moodle)
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, status FROM permintaan_jawaban WHERE id_moodle = ?", (id_moodle,)
        ).fetchone()
        sekarang = datetime.now().isoformat(timespec="seconds")

        if row:
            if row["status"] in ("pending", "proses"):
                return False
            conn.execute(
                "UPDATE permintaan_jawaban SET status = 'pending', dibuat = ?, diproses = NULL WHERE id = ?",
                (sekarang, row["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO permintaan_jawaban (id_moodle, status, dibuat) VALUES (?, 'pending', ?)",
                (id_moodle, sekarang),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def ambil_permintaan_pending():
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM permintaan_jawaban WHERE status = 'pending' ORDER BY id LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def tandai_permintaan(id_baris, status):
    conn = connect()
    try:
        conn.execute(
            "UPDATE permintaan_jawaban SET status = ?, diproses = ? WHERE id = ?",
            (status, datetime.now().isoformat(timespec="seconds"), id_baris),
        )
        conn.commit()
    finally:
        conn.close()


def simpan_jawaban(id_moodle, model, isi):
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO jawaban (id_moodle, model, isi, waktu) VALUES (?, ?, ?, ?)",
            (str(id_moodle), model or "", isi or "", datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


# ==================== ULASAN PM ====================

def simpan_ulasan(id_moodle, penulis, model, isi):
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO ulasan (id_moodle, penulis, model, isi, waktu) VALUES (?, ?, ?, ?, ?)",
            (
                str(id_moodle),
                penulis or "",
                model or "",
                isi or "",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def jumlah_diperiksa():
    """Berapa tugas yang sudah lewat pemeriksaan. Satu tugas dihitung sekali."""
    conn = connect()
    try:
        row = conn.execute("SELECT COUNT(DISTINCT id_moodle) AS n FROM ulasan").fetchone()
        return row["n"] if row else 0
    finally:
        conn.close()


def _self_check():  # pragma: no cover - self check
    # 1. Parsing tenggat format Moodle Indonesia
    assert parse_tenggat("Selasa, 14 Oktober 2026, 23.59") == datetime(2026, 10, 14, 23, 59)
    assert parse_tenggat("Senin, 3 Maret 2025, 8:00") == datetime(2025, 3, 3, 8, 0)
    assert parse_tenggat("") is None
    assert parse_tenggat("besok") is None
    assert parse_tenggat("14 Oktober 2026, 11:30 PM") == datetime(2026, 10, 14, 23, 30)

    # 2. Bobot beban mengikuti sisa waktu
    assert bobot_urgensi(2) == WEIGHT_URGENT
    assert bobot_urgensi(48) == WEIGHT_SOON
    assert bobot_urgensi(200) == WEIGHT_NORMAL
    assert bobot_urgensi(None) == WEIGHT_NORMAL
    assert skor_beban([2, 48, 200]) == WEIGHT_URGENT + WEIGHT_SOON + WEIGHT_NORMAL

    # 3. Hitung beban dari data contoh, tanpa menyentuh DB asli
    contoh = [
        {"mata_kuliah": "Kecerdasan Buatan", "tenggat_dt": (datetime.now() + timedelta(hours=5)).isoformat()},
        {"mata_kuliah": "Kecerdasan Buatan", "tenggat_dt": (datetime.now() + timedelta(hours=50)).isoformat()},
        {"mata_kuliah": "Basis Data", "tenggat_dt": (datetime.now() + timedelta(days=30)).isoformat()},
    ]
    hasil = {}
    for t in contoh:
        jam = sisa_jam(t)
        e = hasil.setdefault(t["mata_kuliah"], {"jumlah": 0, "mendesak": 0, "skor": 0})
        e["jumlah"] += 1
        e["skor"] += bobot_urgensi(jam)
        if jam < URGENT_HOURS:
            e["mendesak"] += 1
    assert hasil["Kecerdasan Buatan"] == {"jumlah": 2, "mendesak": 1, "skor": WEIGHT_URGENT + WEIGHT_SOON}
    assert hasil["Basis Data"]["skor"] == WEIGHT_NORMAL
    print("store.py self-check OK")


if __name__ == "__main__":
    _self_check()
