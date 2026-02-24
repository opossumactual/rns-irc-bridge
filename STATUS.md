# RNS IRC Bridge - Project Status

## Current State: End-to-End Tested, Ready for Deployment

### Completed
- [x] `rns-irc-server.py` — Server bridge (RNS Link → TCP to InspIRCd)
- [x] `rns-irc-client.py` — Client bridge (local TCP → RNS Link to server)
- [x] `config.example.yaml` — Example config for both sides
- [x] `rns-irc-server.service` — systemd unit file
- [x] `requirements.txt` — Python deps (rns, pyyaml)
- [x] `README.md` — Setup and usage docs
- [x] Syntax verified, RNS 1.1.3 API confirmed available
- [x] Git repo initialized, initial commit
- [x] **End-to-end test passed** — Tested with ncat echo server on VM (10.15.1.150),
      bidirectional traffic confirmed through RNS tunnel
- [x] Bug fix: `os.path.expanduser()` for `rns_configdir` in both scripts
- [x] **Real IRC test passed** — InspIRCd on VM + irssi client through RNS tunnel,
      full IRC handshake and operation confirmed (2026-02-24)

### Next Steps
1. Deploy server bridge to DO droplet for production use

### Architecture Notes
- Each IRC session = one RNS Link (no multiplexing)
- Bidirectional `RNS.Buffer` with stream_id 0 for TCP↔RNS bridging
- Persistent server identity file for stable destination hash
- Threading: TCP→RNS in dedicated thread, RNS→TCP via ready_callback
- Periodic re-announces (default 10 min, test config 30s)

### Known Issues
- RNS log output is buffered when running in background (cosmetic)
- Local same-machine testing not possible without rnsd loopback (by design)
- `rns_configdir` paths with `~` require `os.path.expanduser()` (fixed 2026-02-24)
