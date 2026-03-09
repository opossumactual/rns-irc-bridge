# RNS IRC Bridge

A bridge that routes IRC traffic through [Reticulum](https://reticulum.network/)'s encrypted transport layer. No IRC ports are exposed to the public internet — access is only possible through Reticulum.

I recommend using this with [weechat](https://weechat.org/) — the connect.sh script will try to start it.

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
- Optionally install weechat
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

Mobile devices can't run the bridge directly. Instead, run the bridge client on a device your phone can reach over the LAN (a PC, a router, etc.) and point your phone's IRC app at it.

1. Set `listen_host: 0.0.0.0` in your `config.yaml`:
   ```yaml
   client:
     server_destination_hash: <your_hash>
     listen_host: 0.0.0.0
   ```

2. Start the bridge on that machine.

3. Connect your phone's IRC app (Revolution IRC, Goggle, Palaver, LimeChat, etc.) to that machine's LAN IP on port 6667.

Note: Hosted IRC services like IRCCloud won't work — they connect from their servers, not your device.

### Router/Gateway Setup (OpenWrt)

If you have an OpenWrt router already running Reticulum (e.g. GL.iNet Flint2), you can run the bridge client directly on it so all devices on the LAN can connect:

1. Copy the client script to the router (OpenWrt needs the `-O` flag for scp):
   ```bash
   scp -O rns-irc-client.py root@<router_ip>:~/
   ```

2. Install pyyaml on the router:
   ```bash
   pip install pyyaml
   ```

3. Create a config:
   ```bash
   cat > ~/irc-config.yaml << 'EOF'
   client:
     server_destination_hash: <your_hash>
     listen_host: 0.0.0.0
   EOF
   ```

4. Run the bridge:
   ```bash
   python3 ~/rns-irc-client.py -c ~/irc-config.yaml
   ```

Any device on the LAN can then connect an IRC client to the router's IP on port 6667.

## Server Setup

### 1. Install Reticulum and the Bridge

Install Reticulum and set up the bridge server on your VPS/server:

```bash
pip install rns pyyaml
```

Reticulum needs a TCP Server Interface so clients can connect to it over the internet. Edit `~/.reticulum/config` (run `rnsd` once first to generate it) and add an interface:

```
  [[RNS TCP Server]]
    type = TCPServerInterface
    enabled = yes
    listen_ip = 0.0.0.0
    listen_port = 4242
```

Make sure your firewall allows the port (e.g. `ufw allow 4242/tcp`).

Deploy the bridge server:

```bash
mkdir -p /opt/rns-irc-bridge
cp rns-irc-server.py /opt/rns-irc-bridge/
cp rns-irc-server.service /etc/systemd/system/
```

Create the bridge config at `/opt/rns-irc-bridge/config.yaml`:

```yaml
server:
  identity_file: ~/.reticulum/irc_server_identity
  irc_host: 127.0.0.1
  irc_port: 6667
  announce_interval: 600
```

Start the bridge:

```bash
systemctl daemon-reload
systemctl enable --now rns-irc-server
```

The destination hash is printed on first run — share this with clients. Check it with:

```bash
journalctl -u rns-irc-server | grep "Destination hash"
```

### 2. Install InspIRCd

Install InspIRCd and bind it to localhost only:

```bash
apt install inspircd
```

### 3. Configure InspIRCd

Edit `/etc/inspircd/inspircd.conf`. Key settings to change from the defaults:

**Connection limits** — Since all connections arrive from the RNS bridge on `127.0.0.1`, per-IP limits apply to all users combined. The default `localmax="3"` will cap your server at 3 total users:

```xml
<connect allow="127.0.0.1"
         timeout="60"
         pingfreq="120"
         hardsendq="262144"
         softsendq="8192"
         recvq="8192"
         localmax="50"
         globalmax="50"
         maxchannels="20">
```

**Oper access** — Give yourself admin control. Use `host="*@127.0.0.1"` or `host="*@*"`:

```xml
<oper name="yourusername"
      password="your_password"
      host="*@127.0.0.1"
      type="NetAdmin"
      maxchans="60">
```

Then from your IRC client: `/oper yourusername your_password`

**Persistent channels** — Keep channels alive even when empty:

```xml
<module name="permchannels">
<permchannels channel="#yourchannel"
              modes="nt"
              topic="Welcome">
```

**Chat history on join** — Show recent messages to users when they join a channel:

```xml
<module name="chanhistory">
<chanhistory maxlines="50" prefixmsg="yes">
```

**Auto-join** — Put new users in a channel automatically:

```xml
<module name="conn_join">
<autojoin channel="#yourchannel">
```

### 4. Start

```bash
systemctl restart inspircd
systemctl restart rns-irc-server
```

## Troubleshooting

- **"Timed out waiting for path to server"**: Make sure `rnsd` is running and your Reticulum config has a route to the server (TCPClientInterface). Try `rnpath <hash>` to check.

- **Path found but bridge times out**: Kill any existing `rnsd` and let the bridge start its own Reticulum instance, or vice versa — don't run both competing for the same shared instance.

- **Destination hash changed**: The server uses a persistent identity file. If deleted, a new hash is generated. Back up the identity file.

- **"Address already in use" on client**: Something is already listening on port 6667. Check with `ss -tlnp | grep 6667`. If you have an IRC server running on the client machine, stop it — you only need the IRC server on the server side.

- **InspIRCd won't start after config changes**: Check the error with `journalctl -u inspircd -e`. Common issues are missing angle brackets on tags or extra spaces in attribute names.

## License

MIT
