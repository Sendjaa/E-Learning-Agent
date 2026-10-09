"""Teks menu dan bantuan untuk bot Telegram."""

from ..roster import semua_agent

BANTUAN = (
    "📖 <b>Bantuan Hermes</b>\n\n"
    "🛠️ <b>Workshop:</b>\n"
    "/kelas — beban kerja tiap kursi\n"
    "/agent [mata kuliah] — daftar tugas satu kursi\n\n"
    "🔍 <b>Tugas:</b>\n"
    "/cektugas — cek linimasa E-Learning sekarang\n\n"
    "💡 Tombol <b>🤖 Minta Jawaban AI</b> muncul di tiap tugas yang belum dikumpulkan. "
    "Jawaban dibuat oleh kursi yang memegang jenis kerja itu, dan hanya saat kamu klik."
)


def teks_selamat_datang():
    kursi = ", ".join(a["nama"] for a in semua_agent())
    return (
        "🛠️ <b>Hermes — Workshop Kerja</b>\n\n"
        "Saya asisten e-learning kamu. Tiap kursi memegang satu jenis kerja: "
        "tugas kuliah, kode, desain, pengujian, dan pemeriksaan.\n\n"
        f"🪑 <b>Kursi terisi:</b> {kursi}\n\n"
        "Ketik /kelas untuk melihat beban tiap kursi, "
        "atau /cektugas untuk memeriksa tugas aktif."
    )
