#!/usr/bin/env python3
"""Simple TCP port forwarder to mirror Codex proxy onto an alternate port."""

import signal
import socket
import socketserver
import sys
import threading


class ForwardingHandler(socketserver.BaseRequestHandler):
    """Bidirectional TCP forwarding handler."""

    target_host: str = "127.0.0.1"
    target_port: int = 10000

    def handle(self) -> None:  # type: ignore[override]
        try:
            upstream = socket.create_connection((self.target_host, self.target_port))
        except OSError:
            return

        sockets = (self.request, upstream)

        def pipe(src: socket.socket, dst: socket.socket) -> None:
            try:
                while True:
                    chunk = src.recv(65536)
                    if not chunk:
                        break
                    dst.sendall(chunk)
            except OSError:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        threads = [
            threading.Thread(target=pipe, args=(self.request, upstream), daemon=True),
            threading.Thread(target=pipe, args=(upstream, self.request), daemon=True),
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: port_forward.py <local_port> <target_host> <target_port>", file=sys.stderr)
        sys.exit(1)

    local_port = int(sys.argv[1])
    target_host = sys.argv[2]
    target_port = int(sys.argv[3])

    ForwardingHandler.target_host = target_host
    ForwardingHandler.target_port = target_port

    server = ThreadedTCPServer(("127.0.0.1", local_port), ForwardingHandler)

    def shutdown_handler(signum, _frame):  # type: ignore[unused-argument]
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(
        f"Forwarding 127.0.0.1:{local_port} -> {target_host}:{target_port}",
        file=sys.stderr,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
