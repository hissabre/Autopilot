#!/usr/bin/env python3
"""Autopilot — find local businesses without a website, build them one, pitch it, close the deal.

  python run.py cycle            one full pass (what cron runs)
  python run.py loop             run a cycle every hour, forever
  python run.py prospect|enrich|build|deploy|outreach|followup|inbox|call|takedown
  python run.py status           pipeline counts
  python run.py dashboard        web dashboard on :8080
"""
import argparse
import sys
import time
import traceback

from engine import deploy, enrich, inbox, prospect, sitegen, voice
from engine.config import Config
from engine.db import DB
from engine.llm import LLM
from engine.mailer import Mailer


def cycle(cfg, db, llm, mailer):
    steps = [
        ("Inbox — replies first", lambda: inbox.run(cfg, db, llm, mailer)),
        ("Voice call-backs", lambda: voice.run(cfg, db) + voice.sync(cfg, db)),
        ("Take down stale demos", lambda: deploy.takedown_stale(cfg, db)),
        ("Prospect", lambda: prospect.run(cfg, db)),
        ("Enrich (find public email)", lambda: enrich.run(cfg, db, llm)),
        ("Build sites", lambda: sitegen.run(cfg, db, llm)),
        ("Deploy", lambda: deploy.run(cfg, db)),
        ("First emails", lambda: mailer.first_touch()),
        ("Follow-ups", lambda: mailer.followups()),
    ]
    for title, fn in steps:
        print(f"▸ {title}")
        try:
            print(f"  = {fn()}")
        except Exception:  # noqa: BLE001 — one failing step must not stop the others
            traceback.print_exc()
    status(db)


def status(db):
    rows = db.conn.execute("SELECT status, COUNT(*) n FROM prospects GROUP BY status ORDER BY n DESC").fetchall()
    print("\nPipeline: " + " · ".join(f"{r['status']} {r['n']}" for r in rows))
    print(f"Emails sent today: {db.sent_today(Mailer.today(None))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--config")
    ap.add_argument("--every", type=int, default=60, help="minutes between cycles in loop mode")
    a = ap.parse_args()

    cfg = Config(a.config)
    db, llm = DB(), LLM(cfg)
    mailer = Mailer(cfg, db, llm)
    if cfg.dry_run:
        print("DRY RUN — no external calls (fixtures, mock AI, local deploy, .eml outbox)\n")
    elif llm.mock:
        sys.exit("ANTHROPIC_API_KEY missing. Set it in .env, or use DRY_RUN=1.")

    cmds = {
        "cycle": lambda: cycle(cfg, db, llm, mailer),
        "prospect": lambda: prospect.run(cfg, db),
        "enrich": lambda: enrich.run(cfg, db, llm),
        "build": lambda: sitegen.run(cfg, db, llm),
        "deploy": lambda: deploy.run(cfg, db),
        "outreach": lambda: mailer.first_touch(),
        "followup": lambda: mailer.followups(),
        "inbox": lambda: inbox.run(cfg, db, llm, mailer),
        "call": lambda: voice.run(cfg, db) + voice.sync(cfg, db),
        "takedown": lambda: deploy.takedown_stale(cfg, db),
        "status": lambda: status(db),
    }
    if a.cmd == "dashboard":
        from engine.dashboard import create_app
        create_app(cfg).run(host="0.0.0.0", port=8080)
    elif a.cmd == "loop":
        while True:
            cycle(cfg, db, llm, mailer)
            print(f"\n… sleeping {a.every} min\n")
            time.sleep(a.every * 60)
    elif a.cmd in cmds:
        r = cmds[a.cmd]()
        if r is not None:
            print(r)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
