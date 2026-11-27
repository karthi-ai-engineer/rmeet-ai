"""
Max, the bot program (port 3978). Built with Microsoft's Teams SDK for Python, so the same code runs against the
simulated Teams (TEAMS_MODE=sim, default) and real Teams (TEAMS_MODE=teams). Start: `python run.py start`
(or `python -m max.app`).

Step 2: Max says hello when spoken to. No AI yet.
"""

from __future__ import annotations

import asyncio
import logging
import os
import warnings

warnings.filterwarnings("ignore", message=r".*is in preview")  # the SDK announces preview features on import

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from microsoft_teams.api import MessageActivity
from microsoft_teams.api.activities.utils import StripMentionsTextOptions
from microsoft_teams.apps import ActivityContext, App, FastAPIAdapter

from max.config import ROOT, ConfigError, TeamsSettings, load_teams_settings
from max.log import setup_logging
from max.teams.hello import hello_text, should_answer

log = logging.getLogger("max.app")

# The SDK reads these from the environment (and loads .env on import). In simulator mode none of them may apply:
# real credentials would make the SDK fetch a real token and send it to whatever address an unsigned message names.
SIM_UNSAFE_ENV = ("CLIENT_ID", "CLIENT_SECRET", "TENANT_ID", "MANAGED_IDENTITY_CLIENT_ID", "SERVICE_URL",
                  "DANGEROUSLY_ALLOW_UNAUTHENTICATED_REQUESTS", "SKIP_AUTH")
LOCAL_HOSTS = {"127.0.0.1", "::1"}


def _only_this_pc(web: FastAPI) -> None:
    """Simulator mode: answer only direct requests from this PC, JSON only. Blocks tunnels and proxies (they add
    Forwarded headers) and "simple" cross-site form posts from web pages."""

    @web.middleware("http")
    async def guard(request: Request, call_next):
        host = request.client.host if request.client else ""
        if host not in LOCAL_HOSTS or "forwarded" in request.headers or "x-forwarded-for" in request.headers:
            return JSONResponse({"error": "simulator mode: only this PC"}, status_code=403)
        if request.method == "POST" and not request.headers.get("content-type", "").lower().startswith("application/json"):
            return JSONResponse({"error": "send JSON"}, status_code=415)
        return await call_next(request)


def build_app(settings: TeamsSettings) -> tuple[App, FastAPI, uvicorn.Server]:
    web = FastAPI(title="Max")

    @web.get("/health")
    def health():
        return {"ok": True, "teams_mode": settings.teams_mode}

    server = uvicorn.Server(uvicorn.Config(web, host=settings.bot_host, port=settings.bot_port, log_level="warning"))
    options: dict = {"http_server_adapter": FastAPIAdapter(app=web, server_factory=lambda _: server)}
    if settings.teams_mode == "sim":
        # The simulator can't sign messages the way Microsoft does, so signature checks are off. That is safe only
        # because Max then answers this PC alone (127.0.0.1, no proxies) and holds no real credentials.
        for name in SIM_UNSAFE_ENV:
            os.environ.pop(name, None)
        options["dangerously_allow_unauthenticated_requests"] = True
        _only_this_pc(web)
    else:
        # Real Teams: always check Microsoft's signature, whatever the environment says.
        options.update(client_id=settings.client_id, client_secret=settings.client_secret.get_secret_value(),
                       tenant_id=settings.tenant_id, dangerously_allow_unauthenticated_requests=False)
    app = App(**options)

    @app.on_message
    async def on_message(ctx: ActivityContext[MessageActivity]) -> None:
        a = ctx.activity
        conv_type = a.conversation.conversation_type
        mentioned = a.is_recipient_mentioned()
        if not should_answer(conv_type, mentioned):
            return
        a.strip_mentions_text(StripMentionsTextOptions(account_id=a.recipient.id))
        log.info("message in %s from %s", conv_type, a.from_.name)
        await ctx.send(hello_text(a.from_.name))

    return app, web, server


async def serve(settings: TeamsSettings) -> None:
    app, _, _ = build_app(settings)
    await app.start(settings.bot_port)


def main() -> None:
    try:
        settings = load_teams_settings()
    except ConfigError as e:
        raise SystemExit(str(e))
    secrets = [settings.client_secret.get_secret_value()] if settings.client_secret else []
    setup_logging("max", ROOT / "data", secrets=secrets)
    logging.getLogger("microsoft_teams").setLevel(logging.ERROR)  # hides the SDK's expected warnings in sim mode
    log.info("Max starting (%s mode) on %s:%s", settings.teams_mode, settings.bot_host, settings.bot_port)
    asyncio.run(serve(settings))


if __name__ == "__main__":
    main()
