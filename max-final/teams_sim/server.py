"""
The simulated Teams server (port 5100): the Teams screens, a small API for them, live updates, and the fake
Microsoft bot service Max talks to. Start it with `python run.py start`.

  GET  /api/state?as=prince                  who I am, my departments + channels, my chats, everyone
  GET  /api/channels/{id}/threads?as=...     posts with replies
  GET  /api/chats/{id}/messages?as=...
  POST /api/messages                         {as, kind, where, text, thread_id?, quote_id?, mentions?}
  POST /api/reset                            back to the start set
  WS   /api/live?as=prince                   every new/changed message this person can see
  /v3/...                                    the fake Bot Framework service (bot_connector.py)
  /                                          the screens (teams_sim/web/dist)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from teams_sim.cloud import bot_connector, store

# All handlers are async on purpose: they all run on the one event loop, so the single SQLite connection is
# never used by two threads at once (sync handlers would run in a thread pool).

ROOT = Path(__file__).resolve().parents[1]
WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"


class NewMessage(BaseModel):
    as_: str = Field(alias="as")  # the person posting
    kind: str
    where: str
    text: str = ""
    thread_id: str | None = None
    quote_id: str | None = None
    mentions: list[str] = []  # ignored: mentions are always read from the text (@Name of someone in that place)


class Live:
    """Open browser tabs, each playing one person. Sends each change only to people who can see it, to all tabs
    at once. A tab that doesn't take an update in time is closed: it reconnects and reloads by itself, so one
    stuck tab can never hold up everyone else or silently miss updates."""

    def __init__(self, conn, send_timeout: float = 2):
        self.conn = conn
        self.send_timeout = send_timeout
        self.sockets: set[tuple[str, WebSocket]] = set()

    async def send(self, event: dict, kind: str, where: str) -> None:
        await self._send([e for e in list(self.sockets) if store.can_see(self.conn, e[0], kind, where)], event)

    async def send_all(self, event: dict) -> None:
        await self._send(list(self.sockets), event)

    async def _send(self, entries: list, event: dict) -> None:
        async def one(entry):
            try:
                await asyncio.wait_for(entry[1].send_json(event), timeout=self.send_timeout)
            except Exception:  # tab closed or stuck
                self.sockets.discard(entry)
                try:
                    await asyncio.wait_for(entry[1].close(code=1011), timeout=1)
                except Exception:
                    pass

        await asyncio.gather(*(one(e) for e in entries))


def _ignore_closed_tabs(loop) -> None:
    """Windows reports every browser tab that closes its connection as an error; it is normal. Hide only that."""
    previous = loop.get_exception_handler()

    def handler(loop, context):
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        if previous:
            previous(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(handler)


def create_app(db_path: str | Path | None = None, bot_url: str | None = None,
               service_url: str = "http://127.0.0.1:5100/") -> FastAPI:
    """bot_url: where Max listens (None = Max not connected). service_url: this server, as Max should call it."""
    db_path = Path(db_path or ROOT / "data" / "teams_sim.db")
    conn = store.connect(db_path)
    store.drop_unfinished(conn)
    live = Live(conn)
    deliveries: set = set()

    @asynccontextmanager
    async def lifespan(app):
        _ignore_closed_tabs(asyncio.get_running_loop())
        yield
        conn.close()

    app = FastAPI(title="Simulated Teams", lifespan=lifespan)
    app.state.conn, app.state.live = conn, live

    @app.middleware("http")
    async def json_only(request, call_next):
        """Changes must be JSON. A web page can make "simple" cross-site form posts without asking first;
        requiring JSON stops any page open on this PC from posting or resetting behind your back."""
        if request.method in ("POST", "PUT", "PATCH") and                 not request.headers.get("content-type", "").lower().startswith("application/json"):
            return JSONResponse({"detail": "send JSON (Content-Type: application/json)"}, status_code=415)
        return await call_next(request)

    def need_person(pid: str) -> dict:
        try:
            p = store.person(conn, pid)
        except store.NotFound:
            raise HTTPException(404, f"no person {pid!r}")
        if p["is_bot"]:
            raise HTTPException(403, "bots use the Bot Framework API")
        return p

    def need_access(pid: str, kind: str, where: str) -> None:
        need_person(pid)
        if not store.can_see(conn, pid, kind, where):
            raise HTTPException(403, f"{pid} can't see {kind} {where}")

    @app.get("/api/state")
    async def state(as_: str = Query(alias="as")):
        me = need_person(as_)
        return {"me": me, "people": store.people(conn), "teams": store.teams_for(conn, as_), "chats": store.chats_for(conn, as_)}

    @app.get("/api/channels/{cid}/threads")
    async def threads(cid: str, as_: str = Query(alias="as")):
        need_access(as_, "channel", cid)
        return store.channel_threads(conn, cid)

    @app.get("/api/chats/{cid}/messages")
    async def chat_messages(cid: str, as_: str = Query(alias="as")):
        need_access(as_, "chat", cid)
        return store.chat_messages(conn, cid)

    @app.post("/api/messages")
    async def new_message(body: NewMessage):
        need_access(body.as_, body.kind, body.where)
        try:
            mentions = store.find_mentions(conn, body.text, body.kind, body.where)  # only people really tagged
            msg = store.post(conn, body.as_, body.kind, body.where, body.text, thread_id=body.thread_id,
                             quote_id=body.quote_id, mentions=mentions)
        except (store.NotAllowed, store.NotFound) as e:
            raise HTTPException(400, str(e))
        await live.send({"type": "message", "message": msg}, msg["where_kind"], msg["where_id"])
        bot_connector.start_delivery(deliveries, conn, msg, bot_url, service_url)
        return msg

    @app.post("/api/reset")
    async def reset():
        store.reset(conn)
        await live.send_all({"type": "reset"})
        return {"ok": True}

    @app.websocket("/api/live")
    async def live_updates(ws: WebSocket, as_: str = Query(alias="as")):
        try:
            need_person(as_)
        except HTTPException:
            await ws.close(code=4404)
            return
        await ws.accept()
        entry = (as_, ws)
        live.sockets.add(entry)
        try:
            while True:
                await ws.receive_text()  # we only push; reading keeps the connection open
        except WebSocketDisconnect:
            pass
        finally:
            live.sockets.discard(entry)

    app.include_router(bot_connector.make_router(conn, live))

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


def main() -> None:
    """Settings come from the environment (run.py start sets them): TEAMS_SIM_PORT, MAX_BOT_URL, TEAMS_SIM_DB."""
    import uvicorn

    port = int(os.environ.get("TEAMS_SIM_PORT", "5100"))
    app = create_app(db_path=os.environ.get("TEAMS_SIM_DB") or None,
                     bot_url=os.environ.get("MAX_BOT_URL", "http://127.0.0.1:3978/api/messages"),
                     service_url=f"http://127.0.0.1:{port}/")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
