"""
The small start set of the simulated Teams (Thirdwave). The full world (Step 3) replaces this.
Only people's messages: Max's answers are never faked here, Max writes them himself.
"""

PEOPLE = [
    # id, name, role
    ("prince", "Prince", "Product Planning · department lead"),
    ("praga", "Praga", "Procurement · parts buyer"),
    ("rachitaa", "Rachitaa", "Sales · account manager"),
    ("karthi", "Karthi", "IT / AI · Max's developer"),
]
MAX = ("max", "Max", "AI teammate")

TEAMS = [
    # id, name, members, channels: (id, name, private members or None)
    ("planning", "Product Planning", ["prince", "rachitaa", "karthi"], [
        ("pp-general", "General", None),
        ("pp-models", "New models", None),
        ("pp-pricing", "Pricing", None),
        ("pp-budget", "Budget", ["prince", "karthi"]),
    ]),
    ("procurement", "Procurement", ["praga"], [
        ("pr-general", "General", None),
        ("pr-suppliers", "Suppliers", None),
    ]),
    ("sales", "Sales", ["rachitaa"], [
        ("sa-general", "General", None),
        ("sa-accounts", "Big accounts", None),
    ]),
]

CHATS = [
    # id, kind, title, members (Max chats are added for every person automatically)
    ("sync", "group", "New model sync", ["prince", "praga", "rachitaa", "max"]),  # Max was added to this chat
    ("prince-rachitaa", "oneToOne", None, ["prince", "rachitaa"]),
    ("prince-praga", "oneToOne", None, ["prince", "praga"]),
]

# where kind, where id, root key (None = new post / chat message), key, author, UTC time, text
MESSAGES = [
    ("channel", "pp-pricing", None, "t1", "prince", "2026-11-20T05:32:00Z",
     "Decision from today's pricing review: all desktop models go up 5% from 1 Jan, because of the memory price rise. "
     "Rachitaa, please let the big accounts know before 5 Dec."),
    ("channel", "pp-pricing", "t1", "t1r1", "rachitaa", "2026-11-20T05:40:00Z",
     "Noted. Does that include the order we're quoting for Northwind (300 units)?"),
    ("channel", "pp-pricing", "t1", "t1r2", "prince", "2026-11-20T05:52:00Z",
     "Quotes sent before 1 Dec keep the old price."),
    ("channel", "pp-pricing", None, "t2", "praga", "2026-11-24T01:05:00Z",
     "New memory quotes are in the sheet (Parts prices.xlsx › Memory). 32 GB DDR5 is up again this month."),
    ("channel", "pp-models", None, "t3", "prince", "2026-11-18T02:05:00Z",
     "Launch of the new model moves from 8 Jan to Wed 15 Jan: the GPU delivery slipped a week."),
    ("chat", "sync", None, "g1", "praga", "2026-11-26T07:10:00Z",
     "GPU quotes from both suppliers are in. Supplier B is 6% cheaper but ships 2 weeks later."),
    ("chat", "sync", None, "g2", "prince", "2026-11-26T07:14:00Z",
     "2 weeks later breaks the launch date. Let's discuss tomorrow."),
    ("chat", "prince-rachitaa", None, "o1", "prince", "2026-11-27T00:30:00Z",
     "Thanks for picking up the Northwind update."),
    ("chat", "prince-rachitaa", None, "o2", "rachitaa", "2026-11-27T00:31:00Z",
     "Sure, sending it before lunch 🙂"),
    ("chat", "prince-praga", None, "p1", "praga", "2026-11-26T08:02:00Z", "Can we move our 1:1 to 14:30?"),
    ("chat", "prince-praga", None, "p2", "prince", "2026-11-26T08:05:00Z", "Works for me."),
]
