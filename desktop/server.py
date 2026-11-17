"""Local JSON API the desktop UI talks to. Bound to 127.0.0.1 only."""
import imaplib
import json
import os
import platform
import subprocess
import sys
import webbrowser
from datetime import date, timedelta

import requests
from flask import Flask, abort, jsonify, request, send_from_directory

from engine import sitegen
from engine.config import RES, Config, home
from engine.db import DB

from . import startup
from .runner import Runner

UI = RES / "desktop" / "ui"
SECRETS = ["ANTHROPIC_API_KEY", "GOOGLE_PLACES_API_KEY", "RESEND_API_KEY", "NETLIFY_TOKEN",
           "IMAP_USER", "IMAP_PASSWORD", "VAPI_API_KEY", "VAPI_PHONE_NUMBER_ID"]
CONTACTED = ("contacted", "followed_up", "interested", "question", "needs_human", "not_interested",
             "unsubscribed", "bounced", "won", "lost")
REPLIED = ("interested", "question", "needs_human", "not_interested", "won")


def write_env(values: dict):
    path = home() / ".env"
    cur = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                cur[k.strip()] = v.strip()
    for k, v in values.items():
        if k not in SECRETS or v is None:
            continue
        cur[k] = v.strip()
        os.environ[k] = v.strip()
    path.write_text("\n".join(f"{k}={v}" for k, v in cur.items()) + "\n", encoding="utf-8")


def open_path(p):
    if platform.system() == "Windows":
        os.startfile(p)  # noqa: S606
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


def create_app(runner: Runner, token: str):
    app = Flask(__name__, static_folder=None)

    @app.before_request
    def guard():
        # Only the app window gets the per-launch token; blocks other local programs and web pages.
        if request.path.startswith("/api/") and request.headers.get("X-Token") != token:
            abort(403)

    # ── UI ──
    @app.get("/")
    def index():
        return send_from_directory(UI, "index.html")

    @app.get("/ui/<path:f>")
    def ui(f):
        return send_from_directory(UI, f)

    @app.get("/sites/<slug>/")
    def site(slug):
        return send_from_directory(sitegen.SITES_DIR / slug, "index.html")

    # ── state ──
    @app.get("/api/state")
    def state():
        cfg, db = Config(), DB()
        rows = db.all()
        st = {}
        for r in rows:
            st[r["status"]] = st.get(r["status"], 0) + 1
        mrr = {}
        for r in rows:
            if r["status"] == "won":
                mrr[r["currency"] or "CAD"] = mrr.get(r["currency"] or "CAD", 0) + (r["mrr"] or 0)
        contacted = sum(st.get(s, 0) for s in CONTACTED)
        replied = sum(st.get(s, 0) for s in REPLIED)
        today = date.today()
        sends = {r["day"]: r["count"] for r in db.conn.execute("SELECT * FROM sends").fetchall()}
        series = [{"day": (today - timedelta(days=i)).isoformat(),
                   "sent": sends.get((today - timedelta(days=i)).isoformat(), 0)} for i in range(13, -1, -1)]
        ev = db.conn.execute("""SELECT e.*, p.name FROM events e LEFT JOIN prospects p ON p.id=e.prospect_id
                                ORDER BY e.id DESC LIMIT 14""").fetchall()
        secrets_set = {k: bool(os.environ.get(k)) for k in SECRETS}
        setup_done = bool(cfg.get("setup_done"))
        return jsonify({
            "brand": cfg["brand"]["name"], "test_mode": cfg.dry_run, "setup_done": setup_done,
            "markets": [m["city"] for m in cfg.markets()],
            "kpis": {
                "prospects": len(rows), "sites": sum(1 for r in rows if r["site_url"]), "contacted": contacted,
                "reply_rate": round(replied / contacted * 100) if contacted else None,
                "needs_you": st.get("needs_human", 0) + st.get("interested", 0) + st.get("question", 0), "clients": st.get("won", 0),
                "mrr": mrr, "sent_today": db.sent_today(today.isoformat()),
            },
            "funnel": [
                {"id": "found", "label": "Found", "n": len(rows)},
                {"id": "site", "label": "Site built", "n": sum(1 for r in rows if r["site_slug"])},
                {"id": "contacted", "label": "Emailed", "n": contacted},
                {"id": "replied", "label": "Replied", "n": replied},
                {"id": "won", "label": "Clients", "n": st.get("won", 0)},
            ],
            "status_counts": st, "series": series,
            "recent": [{"name": e["name"], "kind": e["kind"], "at": e["at"], "id": e["prospect_id"]} for e in ev],
            "runner": runner.status(), "secrets": secrets_set,
            "startup": startup.is_enabled(), "platform": platform.system(),
        })

    @app.get("/api/leads")
    def leads():
        db = DB()
        rows = db.all()
        out = []
        for r in rows:
            out.append({k: r[k] for k in ("id", "name", "category", "market", "status", "rating", "reviews", "email",
                                          "phone", "site_url", "site_slug", "updated_at", "call_requested", "mrr",
                                          "currency", "plan", "address")})
        return jsonify(out)

    @app.get("/api/leads/<int:pid>")
    def lead(pid):
        cfg, db = Config(), DB()
        r = db.get(pid) or abort(404)
        d = {k: r[k] for k in r.keys() if k not in ("raw",)}
        d["facts"] = json.loads(r["facts"] or "{}")
        d["events"] = [dict(e) for e in db.events(pid)]
        d["plans"] = [{"id": p["id"], "name": p["name"]["en"],
                       "monthly": (p["price"].get(r["currency"]) or next(iter(p["price"].values())))["monthly"]}
                      for p in cfg["plans"]]
        d["local_site"] = f"/sites/{r['site_slug']}/" if r["site_slug"] and (sitegen.SITES_DIR / r["site_slug"]).exists() else None
        d["reply_to"] = cfg["brand"]["reply_to"]
        return jsonify(d)

    @app.post("/api/leads/<int:pid>/<action>")
    def lead_action(pid, action):
        cfg, db = Config(), DB()
        r = db.get(pid) or abort(404)
        body = request.get_json(silent=True) or {}
        if action == "won":
            plan = next(p for p in cfg["plans"] if p["id"] == body.get("plan", cfg["plans"][0]["id"]))
            price = plan["price"].get(r["currency"]) or next(iter(plan["price"].values()))
            db.update(pid, status="won", plan=plan["id"], mrr=price["monthly"])
            db.log(pid, "won", json.dumps({"plan": plan["id"], "mrr": price["monthly"]}))
            runner.log(f"🎉 {r['name']} is now a client ({plan['name']['en']})", "accent")
        elif action == "lost":
            db.update(pid, status="lost")
            db.log(pid, "lost", "marked by you")
        elif action == "handled":
            db.update(pid, status="interested")
            db.log(pid, "handled", "you replied personally")
        elif action == "unsubscribe":
            if r["email"]:
                db.suppress(r["email"], "manual")
            db.update(pid, status="unsubscribed")
            db.log(pid, "unsubscribe", "by you")
        else:
            abort(400)
        return jsonify(ok=True)

    # ── autopilot control ──
    @app.post("/api/autopilot")
    def autopilot():
        b = request.get_json(silent=True) or {}
        cfg = Config()
        runner.set_enabled(bool(b.get("on")), b.get("interval") or cfg.get("interval_min", 60))
        return jsonify(runner.status())

    @app.post("/api/run")
    def run_now():
        return jsonify(started=runner.run_now())

    @app.get("/api/log")
    def log():
        return jsonify(runner.since(int(request.args.get("since", 0))))

    # ── settings ──
    @app.get("/api/settings")
    def get_settings():
        cfg = Config()
        return jsonify({"config": cfg.data, "secrets": {k: bool(os.environ.get(k)) for k in SECRETS},
                        "imap_user": os.environ.get("IMAP_USER", ""), "data_dir": str(home())})

    @app.post("/api/settings")
    def save_settings():
        b = request.get_json(silent=True) or {}
        cfg = Config()
        if "config" in b:
            cfg.data.update(b["config"])
            cfg.save()
        if "secrets" in b:
            write_env({k: v for k, v in b["secrets"].items() if v})
        if "interval_min" in (b.get("config") or {}):
            runner.interval_min = max(15, int(b["config"]["interval_min"]))
        return jsonify(ok=True)

    @app.post("/api/test/<service>")
    def test_service(service):
        b = request.get_json(silent=True) or {}
        key = (b.get("value") or "").strip() or None
        try:
            if service == "ANTHROPIC_API_KEY":
                cfg = Config()
                r = requests.post("https://api.anthropic.com/v1/messages", timeout=20, json={
                    "model": cfg["ai"]["model"], "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]},
                    headers={"x-api-key": key or Config.secret(service), "anthropic-version": "2023-06-01"})
            elif service == "GOOGLE_PLACES_API_KEY":
                r = requests.post("https://places.googleapis.com/v1/places:searchText", timeout=20,
                                  json={"textQuery": "coffee in Vancouver", "pageSize": 1},
                                  headers={"X-Goog-Api-Key": key or Config.secret(service), "X-Goog-FieldMask": "places.id"})
            elif service == "RESEND_API_KEY":
                r = requests.get("https://api.resend.com/domains", timeout=20,
                                 headers={"Authorization": f"Bearer {key or Config.secret(service)}"})
            elif service == "NETLIFY_TOKEN":
                r = requests.get("https://api.netlify.com/api/v1/user", timeout=20,
                                 headers={"Authorization": f"Bearer {key or Config.secret(service)}"})
            elif service == "VAPI_API_KEY":
                r = requests.get("https://api.vapi.ai/phone-number", timeout=20,
                                 headers={"Authorization": f"Bearer {key or Config.secret(service)}"})
            elif service == "IMAP_PASSWORD":
                cfg = Config()
                M = imaplib.IMAP4_SSL(cfg["inbox"]["host"], cfg["inbox"]["port"])
                M.login(b.get("user") or Config.secret("IMAP_USER"), key or Config.secret("IMAP_PASSWORD"))
                M.logout()
                return jsonify(ok=True, msg="Connected to your mailbox")
            else:
                abort(400)
            if r.ok:
                return jsonify(ok=True, msg="Connected")
            return jsonify(ok=False, msg=f"Rejected ({r.status_code}): {r.text[:160]}")
        except Exception as e:  # noqa: BLE001
            return jsonify(ok=False, msg=str(e)[:200])

    # ── system ──
    @app.post("/api/startup")
    def set_startup():
        on = bool((request.get_json(silent=True) or {}).get("on"))
        return jsonify(ok=startup.set_enabled(on), on=startup.is_enabled())

    @app.post("/api/open")
    def open_ext():
        b = request.get_json(silent=True) or {}
        if b.get("what") == "data":
            open_path(home())
        elif b.get("url", "").startswith(("http://", "https://", "mailto:")):
            webbrowser.open(b["url"])
        return jsonify(ok=True)

    @app.post("/api/reset-test")
    def reset_test():
        """Wipe test data (only allowed in test mode) so the user can start fresh."""
        cfg = Config()
        if not cfg.dry_run:
            abort(400)
        db = DB()
        for t in ("prospects", "events", "suppression", "sends", "meta"):
            db.conn.execute(f"DELETE FROM {t}")  # noqa: S608
        db.conn.commit()
        runner.log("Test data cleared", "accent")
        return jsonify(ok=True)

    return app


def free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if __name__ == "__main__":  # dev: python -m desktop.server
    sys.exit("Use desktop/main.py")
