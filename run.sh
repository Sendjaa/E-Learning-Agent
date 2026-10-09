#!/bin/bash
# ============================================
# Hermes Agent — Run Script (semua proses)
# ============================================
# Cara pakai:
#   chmod +x run.sh
#   ./run.sh
#
# Untuk produksi pakai systemd: ./install.sh --install-service
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRIPT_DIR/logs"

# Aktifkan venv
source "$SCRIPT_DIR/venv/bin/activate"

echo "====================================="
echo " Starting Hermes Agent (4 proses)..."
echo "====================================="
echo "Working dir : $SCRIPT_DIR"
echo "Python      : $(which python)"
echo "Log         : $SCRIPT_DIR/logs/"
echo "====================================="
echo ""

PID=""
untuk_hentikan() {
    echo ""
    echo "Menghentikan semua proses..."
    [ -n "$PID" ] && kill $PID 2>/dev/null
    wait
    exit 0
}
trap untuk_hentikan INT TERM

proses() {
    python -m "$1" 2>&1 | tee -a "$SCRIPT_DIR/logs/${1##*.}.log"
}

proses hermes.bot.poller &
proses hermes.scraper.run_check &
proses hermes.brain.worker &
proses hermes.dashboard.server &

PID=$(jobs -p)
wait
