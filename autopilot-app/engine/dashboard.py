"""Small web dashboard: pipeline, revenue, lead detail, mark as won, unsubscribe endpoint, local demo hosting."""
import json
import os
from html import escape as X
from functools import wraps

from flask import Flask, Response, abort, redirect, render_template_string, request, send_from_directory

from .config import Config
from .db import DB
from . import sitegen

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Autopilot</title><style>
body{font:14px/1.5 system-ui,sans-serif;margin:0;background:#f6f5f2;color:#1b1b1b}
.w{max-width:1200px;margin:0 auto;padding:28px 20px}h1{font-size:22px;margin:0 0 18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:22px}
.k{background:#fff;border:1px solid #e6e3dc;border-radius:10px;padding:14px 16px}.k b{font-size:24px;display:block}
.k span{color:#777;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e6e3dc;border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid #f0ede7;vertical-align:top}th{font-size:12px;color:#777;background:#fbfaf8}
.s{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;background:#eee}
.s.interested,.s.won{background:#d7f5e3;color:#0b6b3a}.s.needs_human,.s.question{background:#fff1c9;color:#7a5a00}
.s.unsubscribed,.s.not_interested,.s.bounced,.s.lost{background:#f6dede;color:#8a2a2a}
.s.contacted,.s.followed_up{background:#e2ecff;color:#244a9a}a{color:#244a9a}
pre{white-space:pre-wrap;background:#fff;border:1px solid #eee;padding:10px;border-radius:8px;margin:4px 0 14px}
form{display:inline}select,button{font:inherit;padding:5px 9px}
</style></head><body><div class="w">{{ body|safe }}</div></body></html>"""


def create_app(cfg: Config):
    app = Flask(__name__)
    pw = os.environ.get("DASHBOARD_PASSWORD")

    def auth(f):
        @wraps(f)
        def inner(*a, **k):
            if pw and (not request.authorization or request.authorization.password != pw):
                return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="autopilot"'})
            return f(*a, **k)
        return inner

    @app.get("/")
    @auth
    def home():
        db = DB()
        rows = db.all()
        st = {}
        for r in rows:
            st[r["status"]] = st.get(r["status"], 0) + 1
        mrr = {}
        for r in rows:
            if r["status"] == "won":
                mrr[r["currency"]] = mrr.get(r["currency"], 0) + (r["mrr"] or 0)
        contacted = sum(st.get(s, 0) for s in ("contacted", "followed_up", "interested", "question", "needs_human",
                                               "not_interested", "unsubscribed", "bounced", "won", "lost"))
        replied = sum(st.get(s, 0) for s in ("interested", "question", "needs_human", "not_interested", "won"))
        k = [("Prospects", len(rows)), ("Demo sites live", sum(1 for r in rows if r["site_url"])),
             ("Emailed", contacted), ("Reply rate", f"{(replied / contacted * 100):.0f}%" if contacted else "—"),
             ("Needs you", st.get("needs_human", 0)), ("Clients", st.get("won", 0)),
             ("MRR", " · ".join(f"{v:,.0f} {c}" for c, v in mrr.items()) or "0")]
        html = "<h1>Autopilot</h1><div class=kpis>" + "".join(f"<div class=k><span>{a}</span><b>{b}</b></div>" for a, b in k)
        html += "</div><table><tr><th>Business</th><th>Market</th><th>Status</th><th>Email</th><th>Demo</th><th>Updated</th></tr>"
        for r in rows:
            demo = f"<a target=_blank href='{r['site_url']}'>open</a>" if r["site_url"] else ""
            html += (f"<tr><td><a href='/p/{r['id']}'>{X(r['name'])}</a><br><small>{X(r['category'] or '')} · {r['rating'] or ''}★ "
                     f"({r['reviews'] or 0})</small></td><td>{r['market']}</td><td><span class='s {r['status']}'>{r['status']}</span></td>"
                     f"<td>{X(r['email'] or '')}</td><td>{demo}</td>"
                     f"<td><small>{r['updated_at'][:16]}</small></td></tr>")
        return render_template_string(PAGE, body=html + "</table>")

    @app.get("/p/<int:pid>")
    @auth
    def detail(pid):
        db = DB()
        r = db.get(pid) or abort(404)
        plans = "".join(f"<option value={p['id']}>{p['name']['en']}</option>" for p in cfg["plans"])
        html = (f"<p><a href='/'>← all</a></p><h1>{X(r['name'])}</h1><p>{X(r['address'] or '')}<br>{X(r['phone'] or '')} · {X(r['email'] or 'no email')}"
                f" · <a href='{r['maps_url']}' target=_blank>Maps</a> {'· <a target=_blank href=' + r['site_url'] + '>demo</a>' if r['site_url'] else ''}"
                f"<br>Email source: {X(r['email_source'] or '—')}</p><p>Status: <span class='s {r['status']}'>{r['status']}</span>"
                f"{' · call requested: ' + (r['call_number'] or '') if r['call_requested'] else ''}</p>"
                f"<form method=post action='/won/{pid}'>Mark as client: <select name=plan>{plans}</select> <button>Won</button></form> "
                f"<form method=post action='/lost/{pid}'><button>Lost</button></form><h3>Timeline</h3>")
        for e in db.events(pid):
            html += f"<small>{e['at'][:16]} · <b>{e['kind']}</b></small><pre>{X(e['detail'] or '')}</pre>"
        return render_template_string(PAGE, body=html)

    @app.post("/won/<int:pid>")
    @auth
    def won(pid):
        db = DB()
        r = db.get(pid) or abort(404)
        plan = next(p for p in cfg["plans"] if p["id"] == request.form["plan"])
        cur = r["currency"]
        price = plan["price"].get(cur) or next(iter(plan["price"].values()))
        db.update(pid, status="won", plan=plan["id"], mrr=price["monthly"])
        db.log(pid, "won", json.dumps({"plan": plan["id"], "mrr": price["monthly"], "currency": cur}))
        return redirect(f"/p/{pid}")

    @app.post("/lost/<int:pid>")
    @auth
    def lost(pid):
        DB().update(pid, status="lost")
        return redirect(f"/p/{pid}")

    @app.get("/u")
    def unsubscribe():  # public, no auth — must always work
        e = (request.args.get("e") or "").strip()
        if e:
            db = DB()
            db.suppress(e, "unsubscribe-link")
            r = db.by_email(e)
            if r:
                db.update(r["id"], status="unsubscribed")
                db.log(r["id"], "unsubscribe", "via link")
        return render_template_string(PAGE, body="<h1>You're unsubscribed.</h1><p>You won't hear from us again. "
                                                 "Vous êtes désinscrit, nous ne vous écrirons plus.</p>")

    @app.get("/sites/<slug>/")
    def site(slug):
        return send_from_directory(sitegen.SITES_DIR / slug, "index.html")

    return app
