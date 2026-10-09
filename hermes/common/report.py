"""Penyusun teks laporan kelas — dipakai scraper (setelah cek) dan bot (perintah /kelas)."""

from ..common import store
from ..common.telegram import escape_html
from ..roster import cari_agent, semua_agent

SKALA_BAR = 10


def bar_beban(skor):
    return "█" * min(skor, SKALA_BAR) if skor else "·"


def tugas_agent(agent):
    """Tugas belum dikumpulkan yang ditangani agent ini."""
    return [
        t for t in store.tugas_belum_dikumpul()
        if cari_agent(t.get("mata_kuliah"))["nama"] == agent["nama"]
    ]


def teks_kelas():
    """Papan workshop: satu baris per kursi."""
    beban = store.hitung_beban()
    diperiksa = store.jumlah_diperiksa()
    per_agent = {}
    for mk, data in beban.items():
        nama_agent = cari_agent(mk)["nama"]
        akumulasi = per_agent.setdefault(nama_agent, {"jumlah": 0, "mendesak": 0, "skor": 0})
        for k in akumulasi:
            akumulasi[k] += data[k]

    baris = ["🛠️ <b>WORKSHOP HERMES — BEBAN KERJA</b>", ""]
    for agent in semua_agent():
        data = per_agent.get(agent["nama"])
        # kursi PM kerjaannya memeriksa kursi lain, jadi hasil pemeriksaan ikut jadi bebannya
        periksa = f" | diperiksa: {diperiksa}" if agent.get("pm") else ""
        if not data and not periksa:
            baris.append(f"🪑 <b>{escape_html(agent['nama'])}</b> — kosong, tidak ada tugas")
            continue
        skor = (data or {}).get("skor", 0) + (diperiksa if agent.get("pm") else 0)
        baris.append(
            f"🪑 <b>{escape_html(agent['nama'])}</b>\n"
            f"   {escape_html(agent['mata_kuliah'])} | tugas: {(data or {}).get('jumlah', 0)} | "
            f"mendesak: {(data or {}).get('mendesak', 0)}{periksa}\n"
            f"   beban: {bar_beban(skor)} ({skor})"
        )

    baris.append("")
    baris.append(f"📋 Total tugas belum dikumpulkan: <b>{len(store.tugas_belum_dikumpul())}</b>")
    return "\n".join(baris)


def teks_agent(mk):
    """Daftar tugas yang dipegang agent untuk mata kuliah tertentu."""
    agent = cari_agent(mk)
    daftar = tugas_agent(agent)
    if not daftar:
        return (
            f"🪑 <b>{escape_html(agent['nama'])}</b> tidak punya tugas aktif.\n"
            f"<i>Mata kuliah yang dicari: {escape_html(mk)}</i>"
        )

    baris = [f"🪑 <b>{escape_html(agent['nama'])}</b> — {len(daftar)} tugas aktif", ""]
    for t in daftar:
        jam = store.sisa_jam(t)
        sisa = f"{jam:.0f} jam lagi" if jam is not None else "tenggat tak terbaca"
        baris.append(
            f"📌 <b>{escape_html(t.get('nama'))}</b>\n"
            f"   📚 {escape_html(t.get('mata_kuliah'))}\n"
            f"   ⏰ {escape_html(t.get('tenggat') or '-')} ({sisa})\n"
            f"   🔗 {t.get('link')}"
        )
    return "\n".join(baris)
