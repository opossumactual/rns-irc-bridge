#!/bin/bash
# RNS IRC Bridge - Connect
# Starts the bridge and launches irssi.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting RNS IRC Bridge..."
python3 "$SCRIPT_DIR/rns-irc-client.py" -c "$SCRIPT_DIR/config.yaml" &
BRIDGE_PID=$!

# Wait for the bridge to start listening
sleep 5

if kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "Bridge is running. Launching irssi..."
    irssi -c 127.0.0.1 -p 6667
    kill $BRIDGE_PID 2>/dev/null
else
    echo "Bridge failed to start. Check that rnsd is running."
fi
