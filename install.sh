#!/bin/bash
# ============================================
# Hermes Agent — Install Script for Linux
# ============================================
# Cara pakai:
#   chmod +x install.sh
#   ./install.sh
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="python3"

echo "====================================="
echo " Hermes Agent — Linux Setup"
echo "====================================="

# --- 1. Cek Python ---
if ! command -v $PYTHON &> /dev/null; then
    echo "[ERROR] Python3 tidak ditemukan. Install dulu:"
    echo "  sudo apt update && sudo apt install python3 python3-venv python3-pip -y"
    exit 1
fi

echo "[1/5] Python version: $($PYTHON --version)"

# --- 2. Buat virtual environment ---
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "[2/5] Membuat virtual environment..."
    $PYTHON -m venv "$SCRIPT_DIR/venv"
else
    echo "[2/5] Virtual environment sudah ada."
fi

# Aktifkan venv
source "$SCRIPT_DIR/venv/bin/activate"

# --- 3. Install dependencies ---
echo "[3/5] Install Python dependencies..."
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q

# --- 4. Install Playwright browser ---
echo "[4/5] Install Playwright Chromium browser..."
python -m playwright install chromium

# --- 5. Cek file .env ---
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "[PERINGATAN] File .env tidak ditemukan!"
    echo "  Buat file .env di: $SCRIPT_DIR/.env"
    echo "  Isi dengan:"
    echo "    TELEGRAM_BOT_TOKEN=token_kamu"
    echo "    TELEGRAM_CHAT_ID=chat_id_kamu"
    echo "    OPENROUTER_API_KEY=key_kamu"
    echo "    LLM_MODEL=google/gemini-2.5-flash:free"
    echo "    ELEARNING_URL=https://elearning.kampusmu.ac.id"
    echo "    ELEARNING_USERNAME=username_kamu"
    echo "    PASSWORD=password_kamu"
    echo ""
    echo "  Lalu jalankan: ./run.sh"
    exit 1
fi

echo "[5/5] File .env ditemukan."

# --- 6. Setup systemd service (opsional) ---
if [ "$1" == "--install-service" ]; then
    UNITS=("hermes-bot" "hermes-scraper" "hermes-brain" "hermes-dashboard")
    mkdir -p "$SCRIPT_DIR/logs"

    echo ""
    echo "Installing systemd services: ${UNITS[*]} ..."

    for UNIT in "${UNITS[@]}"; do
        sed "s|__DIR__|$SCRIPT_DIR|g; s|__USER__|$USER|g" \
            "$SCRIPT_DIR/$UNIT.service" \
            | sudo tee "/etc/systemd/system/$UNIT.service" > /dev/null
    done

    sudo systemctl daemon-reload
    for UNIT in "${UNITS[@]}"; do
        sudo systemctl enable "$UNIT"
        sudo systemctl restart "$UNIT"
    done

    echo ""
    echo "[OK] Semua service terinstall!"
    echo "  Status   : sudo systemctl status hermes-bot"
    echo "  Log      : sudo journalctl -u hermes-scraper -f"
    echo "  Dashboard: http://127.0.0.1:8080 (akses lewat SSH tunnel)"
    exit 0
fi

echo ""
echo "====================================="
echo " Setup selesai!"
echo "====================================="
echo ""
echo "Cara jalankan:"
echo "  ./run.sh"
echo ""
echo "Atau install sebagis systemd service (auto-start):"
echo "  ./install.sh --install-service"
echo ""
