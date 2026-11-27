# world/: Thirdwave's simulated world

The history, files and planted facts the simulated Teams starts with (design: `docs/plans/11-sim-world.md`,
step plan: `docs/plans/step-3.md`). Max never reads this folder: the world reaches Max only through the simulated
Teams, exactly like real data would.

| File | What |
|---|---|
| `facts.yaml` | **The fact sheet** (Karthi reviews this): company, people, places, numbers, storylines, dated events, planted facts + traps, canary words, the ~40 files |
| `messages/samples.yaml` | The storyline messages, written by hand around the events (57) |
| `messages/generated.yaml` | The everyday messages (~1,220), written by an AI model and checked by code (`make/write_messages.py`); don't edit by hand |
| `dates.py` | Sliding dates: working-day offsets + Tokyo times, filled in for "today" |
| `model.py` | Loads the fact sheet and checks it is consistent (places, members, the reading window, references, canaries) |
| `make/files.py` | Makes the real files (Excel, PowerPoint, Word, PDF, images); every number comes from `facts.yaml` |
| `make/messages.py` | Makes the messages ready for a day (place, author, time, thread, edited / deleted) |
| `check.py` | Proves every planted fact is exactly where the fact sheet says; canary words only in the private channel |
| `make/write_messages.py` | Writes `generated.yaml` with the AI model: each week sees only what exists by then; strict rules (no numbers, dates, secrets, status changes, files before they exist…) |

**How it works:** git keeps the fact sheet and the message text (with date placeholders like `{date:-3}`). When the
simulated Teams starts or is reset, the loader (`teams_sim/cloud/world.py`) fills in the dates for today and makes the
files; the same day always gives byte-for-byte the same world. Dates count **working days**, so nothing happens on a
weekend, and history always ends today.

**Rules checked by code:** facts Max must answer are at most 19 working days old (inside the 30-day reading window on
any weekday); "older than the window" facts at least 24; authors are members of the place they post in; canary words
(`BLUEHERON`, the budget figures) appear only in Product Planning › Budget.

**Good to know while playing:** the dates slide when the world is loaded: after a new day, press **Reset world**
to bring the history up to today (a restart alone keeps the old dates). When anything in `world/` changes, the
simulated Teams starts from the new world on its next start, and **what you typed while playing is dropped**.

**Commands:** `python run.py world` checks the world for today (facts proven / pending / problems).
`python run.py world-write --plan` shows how the full world's messages would be written; without `--plan` it writes
them with the AI model (cost cap: `[world] generation_budget_usd` in the limits file).
Sample pictures for the review: `docs/plans/pictures/world-sample-*.png`.
