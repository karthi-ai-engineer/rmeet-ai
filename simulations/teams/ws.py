"""Minimal RFC 6455 WebSocket server side for the stdlib HTTP server (used by the media stand-in)."""

import base64
import hashlib
import struct
import threading

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WSClosed(Exception):
    pass


class WebSocket:
    def __init__(self, handler):
        self.h = handler
        self.lock = threading.Lock()
        self.closed = False

    @staticmethod
    def accept(handler) -> "WebSocket | None":
        key = handler.headers.get("Sec-WebSocket-Key")
        if not key or "websocket" not in (handler.headers.get("Upgrade") or "").lower():
            return None
        accept = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        handler.protocol_version = "HTTP/1.1"      # RFC 6455: the upgrade response must be HTTP/1.1 101
        handler.close_connection = True            # never reuse this socket for HTTP afterwards
        handler.send_response(101, "Switching Protocols")
        handler.send_header("Upgrade", "websocket")
        handler.send_header("Connection", "Upgrade")
        handler.send_header("Sec-WebSocket-Accept", accept)
        handler.end_headers()
        handler.wfile.flush()
        return WebSocket(handler)

    def _send(self, opcode: int, payload: bytes) -> None:
        if self.closed:
            raise WSClosed()
        n = len(payload)
        if n < 126:
            head = struct.pack("!BB", 0x80 | opcode, n)
        elif n < 65536:
            head = struct.pack("!BBH", 0x80 | opcode, 126, n)
        else:
            head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
        with self.lock:
            try:
                self.h.wfile.write(head + payload)
                self.h.wfile.flush()
            except OSError:
                self.closed = True
                raise WSClosed()

    def send_text(self, text: str) -> None:
        self._send(0x1, text.encode("utf-8"))

    def send_binary(self, data: bytes) -> None:
        self._send(0x2, data)

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.h.rfile.read(n - len(buf))
            if not chunk:
                raise WSClosed()
            buf += chunk
        return buf

    def recv(self):
        """Returns (opcode, payload). Handles ping/close; raises WSClosed when done."""
        while True:
            b1, b2 = self._read(2)
            opcode, masked, n = b1 & 0x0F, b2 & 0x80, b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if masked else b"\x00\x00\x00\x00"
            data = bytearray(self._read(n))
            for i in range(n):
                data[i] ^= mask[i % 4]
            if opcode == 0x8:
                self.close()
                raise WSClosed()
            if opcode == 0x9:
                self._send(0xA, bytes(data))
                continue
            if opcode == 0xA:
                continue
            return opcode, bytes(data)

    def close(self) -> None:
        if not self.closed:
            try:
                self._send(0x8, b"")
            except WSClosed:
                pass
            self.closed = True
