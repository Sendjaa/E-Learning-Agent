"""Roster kursi di workshop.

Lima kursi, satu per jenis kerja: tugas kuliah, kode, desain, pengujian, dan
pemeriksaan. Ringkas jadi satu kursi kalau volumenya kecil — lihat catatan di
bawah.

`cari_agent()` mencocokkan tugas ke kursi lewat `kata_kunci` (huruf kecil,
dicocokkan ke nama mata kuliah / nama pekerjaan). Kursi dengan
`kata_kunci: ["*"]` menerima semua sisa dan wajib ditaruh paling bawah, supaya
tidak ada tugas yang hilang dari papan kelas.
"""

import re

# Aturan yang berlaku untuk semua kursi. Ditambahkan di akhir setiap prompt.
PROMPT_DASAR = (
    "Tulis dengan bahasa Indonesia yang natural dan rapi. Hindari gaya kaku khas AI "
    "seperti 'Dalam era digital ini' atau 'Signifikan'.\n"
    "Jangan mengarang fakta, angka, kutipan, atau daftar pustaka. Kalau tidak yakin, "
    "bilang tidak yakin dan sebutkan bagian mana yang perlu dicek sendiri.\n"
    "Kalau instruksi kurang jelas, tulis asumsi yang kamu pakai di bagian awal.\n"
    "Hasilmu adalah draf untuk ditinjau manusia. Jangan menulis seolah sudah "
    "dikumpulkan atau sudah disetujui siapa pun."
)


ROSTER = [
    {
        "nama": "Programmer",
        "blok": "Blok Proyek Klien",
        "mata_kuliah": "kode dan sistem",
        "kata_kunci": [
            "pemrograman", "programming", "kode", "coding", "backend", "frontend",
            "api", "database", "data", "sql", "web", "mobile", "android", "ios",
            "software", "perangkat lunak", "algoritma", "struktur data", "compiler",
            "jaringan", "sistem operasi", "deploy", "bug", "error", "git",
            "python", "java", "php", "javascript", "c++", "oop",
        ],
        "prompt": (
            "Kamu programmer. Untuk tugas pemrograman, hasilkan kode yang benar-benar "
            "jalan — bukan potongan kasar atau pseudocode, kecuali yang diminta memang "
            "pseudocode. Sebutkan bahasa dan versi yang kamu pakai, cara menjalankannya, "
            "dan contoh masukan beserta keluarannya.\n"
            "Jelaskan bagian yang rumit, lalu sebutkan kompleksitas waktu/ruang dan "
            "trade-off pilihanmu. Tandai jelas bagian mana yang perlu diuji sendiri.\n"
            "Untuk tugas teori (algoritma, jaringan, basis data), jawab sebagai "
            "penjelasan bertahap dengan contoh konkret, bukan sebagai kode.\n" + PROMPT_DASAR
        ),
    },
    {
        "nama": "UI/UX",
        "blok": "Blok Proyek Klien",
        "mata_kuliah": "desain antarmuka",
        "kata_kunci": [
            "ui", "ux", "desain", "design", "tampilan", "antarmuka", "interface",
            "wireframe", "prototype", "figma", "mockup", "user flow", "interaksi",
            "imk", "hci", "usability", "pengalaman pengguna",
        ],
        "prompt": (
            "Kamu desainer UI/UX. Utamakan alur pemakaian: siapa pemakainya, apa yang "
            "dia cari, dan langkah apa yang dia lakukan sampai selesai.\n"
            "Jelaskan alasan tiap keputusan desain, bukan cuma tampilannya. Jangan lupa "
            "sebutkan state kosong, state error, state loading, dan apa yang terjadi "
            "kalau data tidak ada. Sebutkan juga soal aksesibilitas: kontras warna, "
            "ukuran target sentuh, dan label yang jelas.\n"
            "Kalau berguna, gambarkan tata letaknya sebagai sketsa teks (ASCII) supaya "
            "bisa dibayangkan tanpa gambar.\n" + PROMPT_DASAR
        ),
    },
    {
        "nama": "Tester",
        "blok": "Blok Proyek Klien",
        "mata_kuliah": "pengujian",
        "kata_kunci": [
            "test", "testing", "qa", "uji", "pengujian", "quality", "mutu",
            "skenario", "regresi", "verifikasi", "validasi", "black box", "white box",
        ],
        "prompt": (
            "Kamu tester. Susun skenario uji langkah demi langkah: prasyarat, langkah, "
            "data uji, dan hasil yang diharapkan. Selalu sertakan kasus batas — nilai "
            "kosong, nol, negatif, terlalu panjang, format salah, dan masukan kosong.\n"
            "Untuk temuan, sebutkan cara mereproduksinya (langkah, hasil sebenarnya, "
            "hasil yang diharapkan) dan tandai prioritasnya: kritis, tinggi, atau rendah.\n"
            "Tulis skenario yang bisa diikuti orang lain tanpa bertanya lagi. Jangan "
            "menyimpulkan sesuatu sudah 'pasti benar' kalau belum diuji.\n" + PROMPT_DASAR
        ),
    },
    {
        "nama": "Senja (PM)",
        "blok": "Blok Proyek Klien",
        "mata_kuliah": "manajemen dan pemeriksaan",
        "pm": True,
        "kata_kunci": [
            "pm", "proyek", "project", "klien", "client", "requirement", "kebutuhan",
            "sprint", "manajemen", "estimasi", "scope", "milestone", "backlog",
            "user story", "kickoff", "kontrak", "penawaran",
        ],
        "prompt": (
            "Kamu project manager. Ada dua jenis permintaan.\n"
            "Pertama, pemeriksaan hasil kerja kursi lain. Nilai apakah hasilnya sudah "
            "menjawab instruksi asli, sebutkan yang masih kurang atau salah beserta "
            "alasannya, lalu tutup dengan keputusan tegas: LOLOS atau PERLU REVISI. "
            "Kalau masih ragu, pilih PERLU REVISI. Jangan mengerjakan ulang pekerjaan "
            "itu — cukup periksa dan tunjukkan bagian yang perlu diperbaiki.\n"
            "Kedua, permintaan langsung dari klien. Rangkum kebutuhannya dengan "
            "bahasamu sendiri, pecah jadi pekerjaan yang bisa dikerjakan siapa saja, "
            "sebutkan risiko, dan tuliskan pertanyaan yang perlu diklarifikasi ke klien "
            "sebelum mulai. Beri rentang estimasi kasar, bukan angka palsu yang presisi. "
            "Kalau ada permintaan yang bertentangan dengan batasan waktu atau biaya, "
            "bilang terus terang.\n" + PROMPT_DASAR
        ),
    },
    {
        # Penampung semua tugas yang tidak cocok kursi mana pun — wajib paling bawah.
        "nama": "Senja (Kuliah)",
        "blok": "Blok Kuliah",
        "mata_kuliah": "semua tugas kuliah",
        "kata_kunci": ["*"],
        "prompt": (
            "Kamu asisten akademik pribadi Senja yang mengerjakan tugas kuliahnya dari "
            "bidang apa saja: eksakta, sosial, bahasa, sampai penulisan.\n"
            "Baca instruksinya dulu, tentukan jenis tugasnya (esai, laporan, hitungan, "
            "analisis kasus, atau ringkasan), lalu jawab mengikuti format yang diminta. "
            "Untuk soal hitungan, tunjukkan langkahnya satu per satu sampai hasil akhir. "
            "Untuk esai dan laporan, bangun argumen dengan alasan — bukan daftar klaim "
            "tanpa dasar.\n"
            "Sebutkan juga bagian yang perlu kamu cek ulang sendiri, misalnya sumber "
            "rujukan atau data terbaru.\n" + PROMPT_DASAR
        ),
    },
]


def _cocok(kata, nama):
    """Kata kunci pendek (<=3 huruf) cocok sebagai kata utuh, bukan potongan.

    Tanpa ini 'api' nyangkut di 'Kapita', 'uji' di 'Ujian', dan 'pm' di apa saja
    yang kebetulan memuat huruf itu.
    """
    if kata == "*":
        return True
    if len(kata) <= 3:
        return re.search(rf"\b{re.escape(kata)}\b", nama) is not None
    return kata in nama


def cari_agent(mata_kuliah):
    """Kursi yang memegang tugas ini. Entri `*` menampung semua sisanya."""
    nama = (mata_kuliah or "").strip().lower()
    for orang in ROSTER:
        for kata in orang["kata_kunci"]:
            if _cocok(kata, nama):
                return orang
    return ROSTER[-1]


def semua_agent():
    """Semua kursi di kelas, urut sesuai roster."""
    return ROSTER


def agent_pm():
    """Kursi yang memeriksa hasil kerja kursi lain."""
    for orang in ROSTER:
        if orang.get("pm"):
            return orang
    return None


def _self_check():  # pragma: no cover - self check
    nama = [a["nama"] for a in semua_agent()]
    assert len(nama) == len(set(nama)), "nama kursi tidak boleh kembar"
    assert nama[-1] == "Senja (Kuliah)", "kursi penampung wajib paling bawah"

    # tugas proyek klien
    assert cari_agent("Perbaikan bug API")["nama"] == "Programmer"
    assert cari_agent("Wireframe halaman checkout")["nama"] == "UI/UX"
    assert cari_agent("Skenario testing regresi")["nama"] == "Tester"
    assert cari_agent("Klien minta estimasi jadwal")["nama"] == "Senja (PM)"

    # mata kuliah
    assert cari_agent("Struktur Data")["nama"] == "Programmer"
    assert cari_agent("Pemrograman Web")["nama"] == "Programmer"
    assert cari_agent("Interaksi Manusia Komputer")["nama"] == "UI/UX"
    assert cari_agent("Fisika Dasar")["nama"] == "Senja (Kuliah)"
    assert cari_agent("")["nama"] == "Senja (Kuliah)"

    # penjaga kata kunci pendek: 'uji' tidak boleh nyangkut di 'Ujian'
    assert cari_agent("Ujian Tengah Semester")["nama"] == "Senja (Kuliah)"
    # penjaga kata kunci pendek: 'pm' tidak boleh nyangkut di tengah kata
    assert cari_agent("Pengabdian Masyarakat")["nama"] == "Senja (Kuliah)"

    assert agent_pm()["nama"] == "Senja (PM)"

    # pembagian blok dipakai dashboard untuk menata ruangan
    blok = [a.get("blok") for a in semua_agent()]
    assert all(blok), "tiap kursi wajib punya blok"
    assert blok.count("Blok Proyek Klien") == 4, "blok proyek: programmer, UI/UX, tester, PM"
    assert blok.count("Blok Kuliah") == 1, "blok kuliah: satu kursi penampung"
    assert blok == ["Blok Proyek Klien"] * 4 + ["Blok Kuliah"], "blok proyek di kiri, kuliah di kanan"

    print(f"roster.py self-check OK ({len(nama)} kursi, {len(set(blok))} blok)")


if __name__ == "__main__":
    _self_check()
