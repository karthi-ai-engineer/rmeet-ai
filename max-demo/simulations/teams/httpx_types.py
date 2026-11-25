"""Tiny request/response types so the fake-Microsoft routes are independent of the web server."""

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Req:
    method: str
    path: str                       # already URL-decoded path
    raw_path: str                   # path as received (still percent-encoded)
    query: dict                     # {name: [values]}
    headers: dict                   # lower-case keys
    body: bytes = b""

    def json(self) -> dict:
        try:
            return json.loads(self.body or b"{}")
        except ValueError:
            return {}

    def q(self, name: str, default: str | None = None) -> str | None:
        v = self.query.get(name)
        return v[0] if v else default

    def bearer(self) -> str | None:
        auth = self.headers.get("authorization", "")
        return auth[7:].strip() if auth.lower().startswith("bearer ") else None


@dataclass
class Resp:
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)

    @staticmethod
    def json(status: int, payload, extra: dict | None = None) -> "Resp":
        h = {"Content-Type": "application/json; charset=utf-8", "X-Correlating-OperationId": str(uuid.uuid4())}
        h.update(extra or {})
        return Resp(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), h)

    @staticmethod
    def error(status: int, code: str, message: str) -> "Resp":
        """Bot Connector / Graph style error body."""
        return Resp.json(status, {"error": {"code": code, "message": message,
                                            "innerError": {"request-id": str(uuid.uuid4())}}})


class Router:
    def __init__(self):
        self.routes: list[tuple[str, re.Pattern, Callable]] = []

    def add(self, method: str, pattern: str, fn: Callable) -> None:
        self.routes.append((method, re.compile("^" + pattern + "$"), fn))

    def dispatch(self, req: Req) -> Resp | None:
        for method, rx, fn in self.routes:
            if method != req.method:
                continue
            m = rx.match(req.raw_path)
            if m:
                return fn(req, *m.groups())
        return None
