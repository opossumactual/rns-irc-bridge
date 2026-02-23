# RNS IRC Bridge - Project Status

## Current State: Code Complete, Awaiting VM Testing

### Completed
- [x] `rns-irc-server.py` — Server bridge (RNS Link → TCP to InspIRCd)
- [x] `rns-irc-client.py` — Client bridge (local TCP → RNS Link to server)
- [x] `config.example.yaml` — Example config for both sides
- [x] `rns-irc-server.service` — systemd unit file
- [x] `requirements.txt` — Python deps (rns, pyyaml)
- [x] `README.md` — Setup and usage docs
- [x] Syntax verified, RNS 1.1.3 API confirmed available
- [x] Git repo initialized, initial commit

### Blocked / In Progress
- [ ] **End-to-end test** — Local testing failed because RNS shared instance
      doesn't loop back announces to other local processes on the same machine.
      Need two separate machines (or a VM) for proper testing.

### Next Steps
1. Set up a VM with its own Reticulum instance (`share_instance = No`)
2. Copy `rns-irc-server.py`, `rns-irc-client.py`, `requirements.txt` to VM
3. On VM: install deps, run fake IRC server or InspIRCd on :6667, start server bridge
4. On host: run client bridge pointing at server's destination hash
5. Connect IRC client to localhost:6668 (or whatever port), verify echo works
6. If working, deploy server bridge to DO droplet for real

### Architecture Notes
- Each IRC session = one RNS Link (no multiplexing)
- Bidirectional `RNS.Buffer` with stream_id 0 for TCP↔RNS bridging
- Persistent server identity file for stable destination hash
- Threading: TCP→RNS in dedicated thread, RNS→TCP via ready_callback
- Periodic re-announces (default 10 min, test config 30s)

### Known Issues
- RNS log output is buffered when running in background (cosmetic)
- Local same-machine testing not possible without rnsd loopback (by design)
