# RNS IRC Bridge

A TCP tunnel bridge that routes IRC traffic through Reticulum's encrypted transport layer. No IRC ports are exposed to the public internet — access is only possible through Reticulum.

## Architecture

```
[IRC Client] → localhost:6667 → [rns-irc-client]
        ↓ (Reticulum encrypted transport)
[DO Droplet: rns-irc-server] → 127.0.0.1:6667 → [InspIRCd]
```

Each IRC client connection creates a dedicated RNS Link with its own bidirectional encrypted buffer.

## Prerequisites

- Python 3.10+
- Reticulum installed and configured on both ends
- `rnsd` running on the server (DO droplet) with a TCP Server Interface
- InspIRCd running on the server, bound to `127.0.0.1:6667`
- Reticulum client configured with a TCP Client Interface pointing to the server

## Installation

```bash
pip install -r requirements.txt
```

## Server Setup (DO Droplet)

1. Copy files to the server:
   ```bash
   scp rns-irc-server.py config.example.yaml requirements.txt your-droplet:/opt/rns-irc-bridge/
   ```

2. Install dependencies:
   ```bash
   pip install -r /opt/rns-irc-bridge/requirements.txt
   ```

3. Create config:
   ```bash
   cp /opt/rns-irc-bridge/config.example.yaml /opt/rns-irc-bridge/config.yaml
   # Edit server section as needed
   ```

4. Test manually:
   ```bash
   python3 /opt/rns-irc-bridge/rns-irc-server.py -c /opt/rns-irc-bridge/config.yaml
   ```
   Note the **destination hash** printed on startup — you'll need it for the client.

5. Install systemd service:
   ```bash
   cp rns-irc-server.service /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now rns-irc-server
   ```

6. Check logs:
   ```bash
   journalctl -u rns-irc-server -f
   ```

## Client Setup (Local Machine)

1. Copy config:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. Edit `config.yaml` and set `server_destination_hash` to the hash from the server.

3. Run:
   ```bash
   python3 rns-irc-client.py -c config.yaml
   ```

   Or pass the hash directly:
   ```bash
   python3 rns-irc-client.py abc123def456...
   ```

4. Connect your IRC client (irssi, WeeChat, HexChat, etc.) to `127.0.0.1:6667`.

## How It Works

- **Server bridge** announces a stable Reticulum destination using a persistent identity file. When an RNS Link arrives, it opens a TCP socket to InspIRCd and creates a bidirectional `RNS.Buffer` to shuttle bytes between the Link and the socket.

- **Client bridge** listens on a local TCP port. When an IRC client connects, it establishes an RNS Link to the server's destination hash and creates a matching bidirectional buffer. Data flows: IRC client → TCP → RNS Buffer → Reticulum transport → RNS Buffer → TCP → InspIRCd (and back).

- Each IRC session gets its own Link. Sessions are fully isolated.

## Troubleshooting

- **"Timed out waiting for path to server"**: Ensure `rnsd` is running on both ends, the server has announced, and your Reticulum config has a route to the server's network (e.g., a TCPClientInterface).

- **Connection drops during MOTD/handshake**: This is a stream-based bridge using `RNS.Buffer`, so IRC's chatty handshake should work reliably. If issues occur, check `rnsd` logs for transport errors.

- **Destination hash changed**: The server uses a persistent identity file. If you delete it, a new one is generated with a different hash. Back up your identity file.
