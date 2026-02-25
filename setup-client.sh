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

# Install Python dependencies
echo "[1/3] Installing Python dependencies..."
pip install rns pyyaml --quiet 2>/dev/null || pip install rns pyyaml --break-system-packages --quiet

# Add TCP interface to Reticulum config if not already there
RNS_CONFIG="$HOME/.reticulum/config"
echo "[2/3] Checking Reticulum config..."

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
echo "[3/3] Creating client config..."
cat > "$SCRIPT_DIR/config.yaml" << EOF
client:
  server_destination_hash: "$SERVER_HASH"
  listen_host: 127.0.0.1
  listen_port: 6667
EOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "To connect:"
echo "  1. python3 $SCRIPT_DIR/rns-irc-client.py -c $SCRIPT_DIR/config.yaml"
echo "  2. Point your IRC client at 127.0.0.1:6667"
