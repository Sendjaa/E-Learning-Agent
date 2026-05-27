#!/bin/bash
# ============================================
# Hermes Agent — Run Script
# ============================================
# Cara pakai:
#   chmod +x run.sh
#   ./run.sh
# ============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$SCRIPT_DIR/logs"

# Aktifkan venv
source "$SCRIPT_DIR/venv/bin/activate"

echo "====================================="
echo " Starting Hermes Agent..."
echo "====================================="
echo "Working dir : $SCRIPT_DIR"
echo "Python      : $(which python)"
echo "Log file    : $SCRIPT_DIR/logs/hermes.log"
echo "====================================="
echo ""

# Jalankan dan log ke file + terminal
python "$SCRIPT_DIR/hermes_cloud_agent.py" 2>&1 | tee -a "$SCRIPT_DIR/logs/hermes.log"
