# RNS IRC Bridge

> **Status: In Development** — Functional and tested, but expect rough edges.

A bridge that routes IRC traffic through [Reticulum](https://reticulum.network/)'s encrypted transport layer. No IRC ports are exposed to the public internet — access is only possible through Reticulum.

## Architecture

```
[IRC Client] → localhost:6667 → [rns-irc-client] → (Reticulum encrypted) → [rns-irc-server] → localhost:6667 → [IRC Server]
```

Each IRC client connection gets its own dedicated RNS Link with end-to-end encryption. Multiple clients can connect simultaneously.

## Quick Start (Client)

```bash
git clone https://github.com/opossumactual/rns-irc-bridge.git
cd rns-irc-bridge
./setup-client.sh
./connect.sh
```

The setup script will:
- Install Python dependencies (`rns`, `pyyaml`)
- Add the server's TCP interface to your Reticulum config
- Optionally install irssi
- Optionally allow connections from other devices on your network (for phones, etc.)

## Manual Client Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure your Reticulum config has a TCP interface to the server network.

3. Run the client bridge:
   ```bash
   python3 rns-irc-client.py -c config.yaml
   ```
   Or pass the destination hash directly:
   ```bash
   python3 rns-irc-client.py <destination_hash>
   ```

4. Connect your IRC client to `127.0.0.1:6667`.

## Mobile Clients

Run the client bridge on a machine your phone can reach and set `listen_host: 0.0.0.0` in `config.yaml`. Then connect a mobile IRC app (Igloo, Palaver, LimeChat, etc.) to that machine's IP on port 6667.

Note: Hosted IRC services like IRCCloud won't work — they connect from their servers, not your device.

## Server Setup

1. Install an IRC server (InspIRCd, ngircd, etc.) bound to `127.0.0.1:6667`.

2. Deploy the server bridge:
   ```bash
   mkdir -p /opt/rns-irc-bridge
   cp rns-irc-server.py /opt/rns-irc-bridge/
   cp rns-irc-server.service /etc/systemd/system/
   ```

3. Create server config:
   ```yaml
   server:
     identity_file: /root/.reticulum/irc_server_identity
     irc_host: 127.0.0.1
     irc_port: 6667
     announce_interval: 600
   ```

4. Start:
   ```bash
   systemctl daemon-reload
   systemctl enable --now rns-irc-server
   ```

The destination hash is printed on first run — share this with clients.

## Troubleshooting

- **"Timed out waiting for path to server"**: Make sure `rnsd` is running and your Reticulum config has a route to the server (TCPClientInterface). Try `rnpath <hash>` to check.

- **Path found but bridge times out**: Kill any existing `rnsd` and let the bridge start its own Reticulum instance, or vice versa — don't run both competing for the same shared instance.

- **Destination hash changed**: The server uses a persistent identity file. If deleted, a new hash is generated. Back up the identity file.

## License

MIT
