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
    SERVICE_NAME="hermes-agent"
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

    echo ""
    echo "Installing systemd service: $SERVICE_NAME ..."

    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Hermes E-Learning Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/hermes_cloud_agent.py
Restart=always
RestartSec=10
StandardOutput=append:$SCRIPT_DIR/logs/hermes.log
ErrorOutput=append:$SCRIPT_DIR/logs/hermes_error.log
Environment=PATH=$SCRIPT_DIR/venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    sudo systemctl start "$SERVICE_NAME"

    echo ""
    echo "[OK] Systemd service terinstall!"
    echo "  Status:  sudo systemctl status $SERVICE_NAME"
    echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
    echo "  Restart: sudo systemctl restart $SERVICE_NAME"
    echo "  Log:     sudo journalctl -u $SERVICE_NAME -f"
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
