#!/usr/bin/env python3
"""
RNS IRC Bridge - Server Side

Runs on the same machine as InspIRCd. Announces a Reticulum destination
and bridges incoming RNS Link connections to the local IRC server via TCP.

Each IRC client gets its own RNS Link and its own TCP socket to InspIRCd.
"""

import os
import sys
import time
import signal
import socket
import threading
import argparse

import yaml
import RNS

APP_NAME = "irc"
ASPECT = "server"

DEFAULT_CONFIG = {
    "identity_file": "~/.reticulum/irc_server_identity",
    "irc_host": "127.0.0.1",
    "irc_port": 6667,
    "rns_configdir": None,
    "announce_interval": 600,
}


class IRCServerBridge:
    def __init__(self, config_path=None):
        self.config = dict(DEFAULT_CONFIG)
        if config_path:
            self.config.update(self._load_config(config_path))

        self.reticulum = None
        self.identity = None
        self.destination = None
        self.clients = []  # list of BridgedConnection
        self.clients_lock = threading.Lock()
        self.running = False

    def _load_config(self, path):
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("server", {})

    def start(self):
        self.running = True

        # Initialize Reticulum
        rns_configdir = self.config.get("rns_configdir")
        self.reticulum = RNS.Reticulum(rns_configdir)

        # Load or create a persistent identity
        identity_path = os.path.expanduser(self.config["identity_file"])
        if os.path.isfile(identity_path):
            self.identity = RNS.Identity.from_file(identity_path)
            RNS.log(f"Loaded identity from {identity_path}", RNS.LOG_INFO)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(identity_path)
            RNS.log(f"Created new identity, saved to {identity_path}", RNS.LOG_INFO)

        # Create destination
        self.destination = RNS.Destination(
            self.identity,
            RNS.Destination.IN,
            RNS.Destination.SINGLE,
            APP_NAME,
            ASPECT,
        )
        self.destination.set_link_established_callback(self._link_established)

        # Announce
        self.destination.announce()
        dest_hash = RNS.prettyhexrep(self.destination.hash)
        RNS.log(f"IRC Server Bridge running", RNS.LOG_INFO)
        RNS.log(f"Destination hash: {dest_hash}", RNS.LOG_INFO)
        RNS.log(
            f"Bridging to IRC at {self.config['irc_host']}:{self.config['irc_port']}",
            RNS.LOG_INFO,
        )

        # Periodic announce thread
        announce_interval = self.config.get("announce_interval", 600)
        if announce_interval > 0:
            announce_thread = threading.Thread(
                target=self._announce_loop,
                args=(announce_interval,),
                daemon=True,
            )
            announce_thread.start()

        # Main loop
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _announce_loop(self, interval):
        while self.running:
            time.sleep(interval)
            if self.running and self.destination:
                self.destination.announce()
                RNS.log("Sent periodic announce", RNS.LOG_DEBUG)

    def _link_established(self, link):
        RNS.log(f"New RNS Link from {RNS.prettyhexrep(link.hash)}", RNS.LOG_INFO)
        link.set_link_closed_callback(self._link_closed)

        # Connect to the local IRC server
        try:
            irc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            irc_sock.connect((self.config["irc_host"], self.config["irc_port"]))
            irc_sock.setblocking(True)
        except Exception as e:
            RNS.log(f"Failed to connect to IRC server: {e}", RNS.LOG_ERROR)
            link.teardown()
            return

        # Create bidirectional buffer over the link's channel
        channel = link.get_channel()
        conn = BridgedConnection(link, irc_sock, channel)

        with self.clients_lock:
            self.clients.append(conn)

        conn.start()
        RNS.log(
            f"Bridged connection established (active clients: {len(self.clients)})",
            RNS.LOG_INFO,
        )

    def _link_closed(self, link):
        RNS.log(f"RNS Link closed: {RNS.prettyhexrep(link.hash)}", RNS.LOG_INFO)
        with self.clients_lock:
            for conn in self.clients:
                if conn.link == link:
                    conn.stop()
                    self.clients.remove(conn)
                    break
        RNS.log(f"Active clients: {len(self.clients)}", RNS.LOG_INFO)

    def shutdown(self):
        RNS.log("Shutting down server bridge...", RNS.LOG_INFO)
        self.running = False
        with self.clients_lock:
            for conn in list(self.clients):
                conn.stop()
            self.clients.clear()


class BridgedConnection:
    """Bridges a single RNS Link <-> TCP IRC socket."""

    BUFFER_STREAM_ID = 0

    def __init__(self, link, irc_sock, channel):
        self.link = link
        self.irc_sock = irc_sock
        self.channel = channel
        self.buffer = None
        self.running = False
        self.tcp_to_rns_thread = None
        self._buffer_lock = threading.Lock()

    def start(self):
        self.running = True

        # Create bidirectional RNS buffer
        self.buffer = RNS.Buffer.create_bidirectional_buffer(
            self.BUFFER_STREAM_ID,
            self.BUFFER_STREAM_ID,
            self.channel,
            self._rns_data_ready,
        )

        # Start thread to read from TCP and write to RNS
        self.tcp_to_rns_thread = threading.Thread(
            target=self._tcp_to_rns_loop, daemon=True
        )
        self.tcp_to_rns_thread.start()

    def _rns_data_ready(self, ready_bytes):
        """Called when RNS buffer has data from the remote IRC client."""
        if not self.running:
            return
        try:
            with self._buffer_lock:
                data = self.buffer.read(ready_bytes)
            if data:
                self.irc_sock.sendall(data)
        except Exception as e:
            RNS.log(f"Error forwarding RNS->TCP: {e}", RNS.LOG_ERROR)
            self.stop()

    def _tcp_to_rns_loop(self):
        """Read from IRC TCP socket and write to RNS buffer."""
        try:
            while self.running:
                data = self.irc_sock.recv(4096)
                if not data:
                    RNS.log("IRC server closed connection", RNS.LOG_INFO)
                    break
                with self._buffer_lock:
                    self.buffer.write(data)
                    self.buffer.flush()
        except Exception as e:
            if self.running:
                RNS.log(f"Error in TCP->RNS loop: {e}", RNS.LOG_ERROR)
        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return
        self.running = False

        try:
            self.irc_sock.close()
        except Exception:
            pass

        try:
            if self.buffer:
                self.buffer.close()
        except Exception:
            pass

        try:
            if self.link and self.link.status == RNS.Link.ACTIVE:
                self.link.teardown()
        except Exception:
            pass

        RNS.log("Bridged connection closed", RNS.LOG_INFO)


def main():
    parser = argparse.ArgumentParser(description="RNS IRC Bridge - Server")
    parser.add_argument(
        "-c", "--config", default=None, help="Path to config.yaml"
    )
    args = parser.parse_args()

    bridge = IRCServerBridge(config_path=args.config)

    def signal_handler(sig, frame):
        bridge.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bridge.start()


if __name__ == "__main__":
    main()
