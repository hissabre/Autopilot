"""Background autopilot: runs the pipeline on a timer inside the app, with a live log the UI can stream."""
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timedelta

from engine import deploy, enrich, inbox, prospect, sitegen, voice
from engine.config import Config
from engine.db import DB
from engine.llm import LLM
from engine.mailer import Mailer

STEPS = [
    ("inbox", "Reading replies"),
    ("voice", "Call-backs"),
    ("takedown", "Cleaning up old demos"),
    ("prospect", "Finding businesses"),
    ("enrich", "Finding contact emails"),
    ("build", "Designing websites"),
    ("deploy", "Publishing websites"),
    ("outreach", "Sending emails"),
    ("followup", "Following up"),
]


class Runner:
    def __init__(self):
        self.log_lines = deque(maxlen=2000)
        self.seq = 0
        self.lock = threading.Lock()
        self.running = False          # a cycle is executing right now
        self.enabled = False          # autopilot timer on
        self.step = None
        self.last_run = None
        self.next_run = None
        self.interval_min = 60
        self._wake = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    # ── log ──
    def log(self, msg="", level="info"):
        msg = str(msg).rstrip()
        if not msg:
            return
        with self.lock:
            self.seq += 1
            self.log_lines.append({"n": self.seq, "t": datetime.now().strftime("%H:%M:%S"), "level": level,
                                   "msg": msg.strip()})

    def since(self, n: int):
        with self.lock:
            return [l for l in self.log_lines if l["n"] > n]

    # ── control ──
    def set_enabled(self, on: bool, interval_min: int | None = None):
        if interval_min:
            self.interval_min = max(15, int(interval_min))
        self.enabled = on
        self.next_run = datetime.now() if on else None
        self.log("Autopilot switched ON" if on else "Autopilot paused", "accent")
        self._wake.set()

    def run_now(self):
        if self.running:
            return False
        threading.Thread(target=self.cycle, daemon=True).start()
        return True

    def status(self):
        return {
            "enabled": self.enabled, "running": self.running, "step": self.step,
            "last_run": self.last_run.isoformat(timespec="seconds") if self.last_run else None,
            "next_run": self.next_run.isoformat(timespec="seconds") if self.next_run else None,
            "interval_min": self.interval_min, "steps": [{"id": s, "label": l} for s, l in STEPS],
        }

    def _loop(self):
        while True:
            self._wake.wait(timeout=20)
            self._wake.clear()
            if self.enabled and not self.running and self.next_run and datetime.now() >= self.next_run:
                self.cycle()

    # ── one pass ──
    def cycle(self):
        if self.running:
            return
        self.running = True
        try:
            cfg = Config()
            db, llm = DB(), LLM(cfg)
            if not cfg.dry_run and llm.mock:
                self.log("Claude API key missing — add it in Settings → Connections, or switch on Test mode.", "error")
                return
            mailer = Mailer(cfg, db, llm)
            self.log(f"Run started{' (test mode — nothing real is sent)' if cfg.dry_run else ''}", "accent")
            if cfg.dry_run:
                inbox.simulate_replies(cfg, db)
            fns = {
                "inbox": lambda: inbox.run(cfg, db, llm, mailer, log=self.log),
                "voice": lambda: voice.run(cfg, db, log=self.log) + voice.sync(cfg, db, log=self.log),
                "takedown": lambda: deploy.takedown_stale(cfg, db, log=self.log),
                "prospect": lambda: prospect.run(cfg, db, log=self.log),
                "enrich": lambda: enrich.run(cfg, db, llm, log=self.log),
                "build": lambda: sitegen.run(cfg, db, llm, log=self.log),
                "deploy": lambda: deploy.run(cfg, db, log=self.log),
                "outreach": lambda: mailer.first_touch(log=self.log),
                "followup": lambda: mailer.followups(log=self.log),
            }
            for sid, label in STEPS:
                self.step = sid
                try:
                    fns[sid]()
                except Exception as e:  # noqa: BLE001 — one failing step must not stop the rest
                    self.log(f"{label}: {e}", "error")
                    traceback.print_exc()
                time.sleep(0.15)
            self.log("Run finished", "accent")
        except Exception as e:  # noqa: BLE001
            self.log(f"Run failed: {e}", "error")
        finally:
            self.step = None
            self.running = False
            self.last_run = datetime.now()
            if self.enabled:
                self.next_run = self.last_run + timedelta(minutes=self.interval_min)
