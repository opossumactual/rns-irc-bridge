#!/bin/bash
# RNS IRC Bridge - Client Setup
# Installs dependencies, configures Reticulum, and creates client config.

set -e

SERVER_HASH="b44e0b2a564aaa7c5117ce38f38dc3e7"
SERVER_HOST="rns.notconfnet.us"
SERVER_PORT="4242"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== RNS IRC Bridge Client Setup ==="
echo ""

# Detect package manager
if command -v apt &>/dev/null; then
    PKG_MGR="apt"
    PKG_INSTALL="sudo apt install -y"
elif command -v pacman &>/dev/null; then
    PKG_MGR="pacman"
    PKG_INSTALL="sudo pacman -S --noconfirm"
elif command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
    PKG_INSTALL="sudo dnf install -y"
else
    PKG_MGR="unknown"
fi

# Install Python dependencies
echo "[1/5] Installing Python dependencies..."
pip install rns pyyaml --quiet 2>/dev/null || pip install rns pyyaml --break-system-packages --quiet

# Add TCP interface to Reticulum config if not already there
RNS_CONFIG="$HOME/.reticulum/config"
echo "[2/5] Checking Reticulum config..."

if [ ! -f "$RNS_CONFIG" ]; then
    echo "  No Reticulum config found. Running rnsd once to generate it..."
    rnsd &
    sleep 2
    kill $! 2>/dev/null || true
fi

if grep -q "$SERVER_HOST" "$RNS_CONFIG" 2>/dev/null; then
    echo "  Interface to $SERVER_HOST already configured."
else
    echo "  Adding TCP interface to $SERVER_HOST..."
    cat >> "$RNS_CONFIG" << EOF

  [[RNS IRC Server]]
    type = TCPClientInterface
    enabled = yes
    target_host = $SERVER_HOST
    target_port = $SERVER_PORT
EOF
    echo "  Added."
fi

# Create client config
echo "[3/5] Creating client config..."
echo ""
echo "  Allow connections from other devices on your network?"
echo "  (Needed for connecting from a phone or another machine)"
echo "  1) No, localhost only (127.0.0.1)"
echo "  2) Yes, accept from any device (0.0.0.0)"
echo ""
read -p "  Choice [1/2]: " listen_choice

if [ "$listen_choice" = "2" ]; then
    LISTEN_HOST="0.0.0.0"
else
    LISTEN_HOST="127.0.0.1"
fi

cat > "$SCRIPT_DIR/config.yaml" << EOF
client:
  server_destination_hash: "$SERVER_HASH"
  listen_host: $LISTEN_HOST
  listen_port: 6667
EOF

# IRC client
echo "[4/5] IRC client..."
echo ""
echo "  Do you want to install irssi (terminal IRC client)?"
echo "  1) Yes, install irssi"
echo "  2) No, I'll use my own IRC client"
echo ""
read -p "  Choice [1/2]: " choice

if [ "$choice" = "1" ]; then
    if command -v irssi &>/dev/null; then
        echo "  irssi is already installed."
    elif [ "$PKG_MGR" != "unknown" ]; then
        echo "  Installing irssi..."
        $PKG_INSTALL irssi
    else
        echo "  Could not detect package manager. Install irssi manually."
    fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "To connect:"
echo "  1. python3 $SCRIPT_DIR/rns-irc-client.py -c $SCRIPT_DIR/config.yaml"
echo "  2. In another terminal: irssi -c 127.0.0.1 -p 6667"
if [ "$LISTEN_HOST" = "0.0.0.0" ]; then
    echo ""
    echo "  Remote devices can connect their IRC client to this machine's IP on port 6667."
fi
