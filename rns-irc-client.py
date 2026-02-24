#!/usr/bin/env python3
"""
RNS IRC Bridge - Client Side

Runs on the user's local machine. Listens on a local TCP port for IRC client
connections and bridges each one over a separate RNS Link to the server bridge.
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
    "server_destination_hash": None,
    "listen_host": "127.0.0.1",
    "listen_port": 6667,
    "rns_configdir": None,
    "path_request_timeout": 30,
}


class IRCClientBridge:
    def __init__(self, config_path=None, dest_hash_override=None):
        self.config = dict(DEFAULT_CONFIG)
        if config_path:
            self.config.update(self._load_config(config_path))
        if dest_hash_override:
            self.config["server_destination_hash"] = dest_hash_override

        if not self.config.get("server_destination_hash"):
            RNS.log("No server destination hash configured", RNS.LOG_ERROR)
            sys.exit(1)

        self.reticulum = None
        self.server_dest_hash = None
        self.listen_sock = None
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = False

    def _load_config(self, path):
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("client", {})

    def start(self):
        self.running = True

        # Parse destination hash
        dest_hex = self.config["server_destination_hash"].replace(":", "").replace(" ", "")
        dest_len = (RNS.Reticulum.TRUNCATED_HASHLENGTH // 8) * 2
        if len(dest_hex) != dest_len:
            RNS.log(
                f"Invalid destination hash length: expected {dest_len} hex chars, got {len(dest_hex)}",
                RNS.LOG_ERROR,
            )
            sys.exit(1)
        self.server_dest_hash = bytes.fromhex(dest_hex)

        # Initialize Reticulum
        rns_configdir = self.config.get("rns_configdir")
        if rns_configdir:
            rns_configdir = os.path.expanduser(rns_configdir)
        self.reticulum = RNS.Reticulum(rns_configdir)

        # Request path to server if we don't have one
        if not RNS.Transport.has_path(self.server_dest_hash):
            RNS.log("Requesting path to server...", RNS.LOG_INFO)
            RNS.Transport.request_path(self.server_dest_hash)
            timeout = self.config.get("path_request_timeout", 30)
            start = time.time()
            while not RNS.Transport.has_path(self.server_dest_hash):
                time.sleep(0.5)
                if time.time() - start > timeout:
                    RNS.log(
                        "Timed out waiting for path to server. Is the server running and announced?",
                        RNS.LOG_ERROR,
                    )
                    sys.exit(1)

        RNS.log("Path to server found", RNS.LOG_INFO)

        # Start TCP listener
        listen_host = self.config["listen_host"]
        listen_port = self.config["listen_port"]
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.bind((listen_host, listen_port))
        self.listen_sock.listen(5)
        self.listen_sock.settimeout(1.0)

        RNS.log(
            f"IRC Client Bridge listening on {listen_host}:{listen_port}",
            RNS.LOG_INFO,
        )
        RNS.log(
            f"Bridging to server {RNS.prettyhexrep(self.server_dest_hash)}",
            RNS.LOG_INFO,
        )
        RNS.log("Connect your IRC client to this address", RNS.LOG_INFO)

        # Accept loop
        try:
            while self.running:
                try:
                    client_sock, addr = self.listen_sock.accept()
                    RNS.log(f"IRC client connected from {addr}", RNS.LOG_INFO)
                    handler = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, addr),
                        daemon=True,
                    )
                    handler.start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _handle_client(self, client_sock, addr):
        """Handle a single IRC client connection by establishing an RNS Link."""
        # Recall the server identity
        server_identity = RNS.Identity.recall(self.server_dest_hash)
        if not server_identity:
            RNS.log("Cannot recall server identity. Try again after an announce.", RNS.LOG_ERROR)
            client_sock.close()
            return

        # Build the server destination
        server_destination = RNS.Destination(
            server_identity,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            APP_NAME,
            ASPECT,
        )

        # Establish RNS Link
        link = RNS.Link(server_destination)

        conn = ClientBridgedConnection(link, client_sock, addr)

        with self.clients_lock:
            self.clients.append(conn)

        # Set callbacks
        link.set_link_established_callback(conn.link_established)
        link.set_link_closed_callback(conn.link_closed)

        # Wait for link establishment or timeout
        timeout = 30
        start = time.time()
        while not conn.is_ready() and not conn.is_failed() and time.time() - start < timeout:
            time.sleep(0.1)

        if not conn.is_ready():
            RNS.log(f"Link establishment timed out for {addr}", RNS.LOG_ERROR)
            conn.stop()
            with self.clients_lock:
                if conn in self.clients:
                    self.clients.remove(conn)

    def shutdown(self):
        RNS.log("Shutting down client bridge...", RNS.LOG_INFO)
        self.running = False

        if self.listen_sock:
            try:
                self.listen_sock.close()
            except Exception:
                pass

        with self.clients_lock:
            for conn in list(self.clients):
                conn.stop()
            self.clients.clear()


class ClientBridgedConnection:
    """Bridges a single local TCP IRC client <-> RNS Link to the server."""

    BUFFER_STREAM_ID = 0

    def __init__(self, link, tcp_sock, addr):
        self.link = link
        self.tcp_sock = tcp_sock
        self.addr = addr
        self.buffer = None
        self.channel = None
        self.running = True
        self._ready = False
        self._failed = False
        self.tcp_to_rns_thread = None
        self._buffer_lock = threading.Lock()

    def is_ready(self):
        return self._ready

    def is_failed(self):
        return self._failed

    def link_established(self, link):
        """Called when the RNS Link is ready."""
        RNS.log(f"RNS Link established for {self.addr}", RNS.LOG_INFO)

        self.channel = link.get_channel()
        self.buffer = RNS.Buffer.create_bidirectional_buffer(
            self.BUFFER_STREAM_ID,
            self.BUFFER_STREAM_ID,
            self.channel,
            self._rns_data_ready,
        )

        # Start TCP->RNS forwarding thread
        self.tcp_to_rns_thread = threading.Thread(
            target=self._tcp_to_rns_loop, daemon=True
        )
        self.tcp_to_rns_thread.start()

        self._ready = True

    def link_closed(self, link):
        """Called when the RNS Link is torn down."""
        reason = "unknown"
        if link.teardown_reason == RNS.Link.TIMEOUT:
            reason = "timeout"
        elif link.teardown_reason == RNS.Link.DESTINATION_CLOSED:
            reason = "server closed"
        elif link.teardown_reason == RNS.Link.INITIATOR_CLOSED:
            reason = "client closed"
        RNS.log(f"RNS Link closed for {self.addr}: {reason}", RNS.LOG_INFO)
        self._failed = True
        self.stop()

    def _rns_data_ready(self, ready_bytes):
        """Called when RNS buffer has data from the IRC server."""
        if not self.running:
            return
        try:
            with self._buffer_lock:
                data = self.buffer.read(ready_bytes)
            if data:
                self.tcp_sock.sendall(data)
        except Exception as e:
            RNS.log(f"Error forwarding RNS->TCP for {self.addr}: {e}", RNS.LOG_ERROR)
            self.stop()

    def _tcp_to_rns_loop(self):
        """Read from local IRC client and write to RNS buffer."""
        try:
            while self.running:
                data = self.tcp_sock.recv(4096)
                if not data:
                    RNS.log(f"IRC client {self.addr} disconnected", RNS.LOG_INFO)
                    break
                with self._buffer_lock:
                    self.buffer.write(data)
                    self.buffer.flush()
        except Exception as e:
            if self.running:
                RNS.log(f"Error in TCP->RNS loop for {self.addr}: {e}", RNS.LOG_ERROR)
        finally:
            self.stop()

    def stop(self):
        if not self.running:
            return
        self.running = False

        try:
            self.tcp_sock.close()
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

        RNS.log(f"Bridged connection closed for {self.addr}", RNS.LOG_INFO)


def main():
    parser = argparse.ArgumentParser(description="RNS IRC Bridge - Client")
    parser.add_argument(
        "-c", "--config", default=None, help="Path to config.yaml"
    )
    parser.add_argument(
        "destination",
        nargs="?",
        default=None,
        help="Server destination hash (overrides config)",
    )
    args = parser.parse_args()

    bridge = IRCClientBridge(
        config_path=args.config,
        dest_hash_override=args.destination,
    )

    def signal_handler(sig, frame):
        bridge.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    bridge.start()


if __name__ == "__main__":
    main()
