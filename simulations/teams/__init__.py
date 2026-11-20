"""
Fake Microsoft Teams platform for rmeet-ai.

Imitates the real contracts so Max's Teams code runs unchanged:
  identity.py   - Entra token endpoint + Bot Framework OpenID/JWKS + JWT signing
  store.py      - tenant, team, channel, users, messages, files, app installation
  connector.py  - Bot Connector REST API (/teams/v3/...) + delivery of activities to the bot
  graph.py      - Microsoft Graph subset (/graph/v1.0/...) for channel messages and files
See docs/research/teams/*.md for the contracts these follow.
"""
