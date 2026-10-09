"""Proses dashboard: server HTTP kecil untuk workshop animasi.

Hanya bind ke localhost. Untuk melihat dari luar, pakai SSH tunnel:
    ssh -L 8080:127.0.0.1:8080 user@server

Jalankan:
    python -m hermes.dashboard.server
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..common import store
from ..common.config import DASHBOARD_HOST, DASHBOARD_PORT
from ..roster import cari_agent, semua_agent

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def state():
    """Keadaan kelas: satu kursi per agent, lengkap dengan tugas dan beban."""
    beban = store.hitung_beban()
    belum = store.tugas_belum_dikumpul()

    per_agent = {}
    for t in belum:
        nama_agent = cari_agent(t.get("mata_kuliah"))["nama"]
        entri = per_agent.setdefault(nama_agent, {"jumlah": 0, "mendesak": 0, "skor": 0, "tugas": []})
        jam = store.sisa_jam(t)
        entri["jumlah"] += 1
        entri["skor"] += store.bobot_urgensi(jam)
        if jam is not None and jam < store.URGENT_HOURS:
            entri["mendesak"] += 1
        entri["tugas"].append({
            "nama": t.get("nama"),
            "mata_kuliah": t.get("mata_kuliah"),
            "tenggat": t.get("tenggat"),
            "sisa_jam": None if jam is None else round(jam, 1),
            "link": t.get("link"),
        })

    kursi = []
    diperiksa = store.jumlah_diperiksa()
    for agent in semua_agent():
        data = per_agent.get(agent["nama"], {"jumlah": 0, "mendesak": 0, "skor": 0, "tugas": []})
        data["tugas"].sort(key=lambda x: (x["sisa_jam"] is None, x["sisa_jam"]))
        # kursi PM kerjaannya memeriksa kursi lain, jadi hasil pemeriksaan ikut jadi bebannya
        kursi.append({
            "nama": agent["nama"],
            "blok": agent.get("blok", "Kelas"),
            "mata_kuliah": agent["mata_kuliah"],
            "jumlah": data["jumlah"],
            "mendesak": data["mendesak"],
            "skor": data["skor"] + (diperiksa if agent.get("pm") else 0),
            "diperiksa": diperiksa if agent.get("pm") else None,
            "tugas": data["tugas"],
        })

    return {
        "diperbarui": datetime.now().isoformat(timespec="seconds"),
        "terakhir_cek": store.terakhir_cek(),
        "total_tugas": len(belum),
        "skor_maks": max([k["skor"] for k in kursi], default=0),
        "kursi": kursi,
    }


class Handler(BaseHTTPRequestHandler):
    def _kirim(self, status, tipe, isi):
        self.send_response(status)
        self.send_header("Content-Type", tipe)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(isi)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            body = json.dumps(state(), ensure_ascii=False).encode("utf-8")
            self._kirim(200, "application/json; charset=utf-8", body)
            return

        if self.path in ("/", "/index.html"):
            index = os.path.join(STATIC_DIR, "index.html")
            try:
                with open(index, "rb") as f:
                    self._kirim(200, "text/html; charset=utf-8", f.read())
            except OSError:
                self._kirim(404, "text/plain; charset=utf-8", b"index.html tidak ditemukan")
            return

        self._kirim(404, "text/plain; charset=utf-8", b"Tidak ditemukan")

    def log_message(self, *args):
        pass  # jangan banjiri log systemd dengan tiap request


def main():
    store.init_db()
    server = ThreadingHTTPServer((DASHBOARD_HOST, DASHBOARD_PORT), Handler)
    print(f"[Dashboard] Workshop Hermes di http://{DASHBOARD_HOST}:{DASHBOARD_PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
