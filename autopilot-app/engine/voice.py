"""Optional — AI voice call-backs (Vapi). ONLY for leads who replied and asked for a call or gave a number.

Never use this for cold calls: AI-voice calls without prior express consent are illegal in the US
(TCPA, FCC Feb 2024 ruling) and restricted in Canada (CRTC Unsolicited Telecommunications Rules).
"""
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

from .config import Config
from .db import DB
from .mailer import plans_text

VAPI = "https://api.vapi.ai"

SCRIPT = {
    "en": """You are {sender}'s assistant at {brand}, a small web studio, calling {name} BECAUSE THEY ASKED FOR A CALL
by email about the free demo website we built for them ({url}). Start by saying who you are, that you're an AI
assistant, and that they asked for a call. Be brief, warm and natural. Goals: answer questions, explain the plans,
and if they want to go ahead, confirm their preferred plan and the email to send the payment link to.
Plans: {plans}. Never invent prices or promises. If they want to stop, apologise and end the call.""",
    "fr": """Vous êtes l'assistant de {sender} chez {brand}, un petit studio web. Vous appelez {name} PARCE QU'ILS ONT
DEMANDÉ UN APPEL par email au sujet du site de démonstration gratuit ({url}). Présentez-vous, dites que vous êtes un
assistant IA et qu'ils ont demandé cet appel. Soyez bref, chaleureux et naturel. Objectifs : répondre aux questions,
présenter les formules, et s'ils veulent commencer, confirmer la formule et l'email pour le lien de paiement.
Formules : {plans}. N'inventez jamais de prix ni de promesses. S'ils veulent arrêter, excusez-vous et raccrochez.""",
}


DIAL = {"CA": "1", "US": "1", "ML": "223", "CI": "225", "SN": "221", "BF": "226", "FR": "33"}


def e164(raw: str, country: str) -> str:
    d = re.sub(r"[^\d+]", "", raw)
    if d.startswith("+"):
        return d
    if d.startswith("00"):
        return "+" + d[2:]
    cc = DIAL.get(country, "")
    if cc == "1" and len(d) == 11 and d.startswith("1"):
        return "+" + d
    return f"+{cc}{d}"


def _h():
    return {"Authorization": f"Bearer {Config.secret('VAPI_API_KEY')}", "Content-Type": "application/json"}


def run(cfg: Config, db: DB, log=print) -> int:
    if not cfg["voice"]["enabled"]:
        return 0
    n = 0
    for row in db.by_status("interested", "question", "needs_human"):
        if not row["call_requested"] or row["called_at"] or not row["call_number"]:
            continue
        market = cfg.market(row["market"])
        local = datetime.now(ZoneInfo(market["timezone"]))
        a, b = cfg["voice"]["call_window_local"]
        if not cfg.dry_run and not (local.weekday() < 5 and a <= local.hour < b):
            continue
        lang = market["language"]
        number = e164(row["call_number"], market["country"])
        brand = cfg["brand"]
        assistant = {
            "firstMessage": (f"Bonjour, ici l'assistant IA de {brand['sender_name']} chez {brand['name']}. Vous aviez demandé "
                             f"qu'on vous rappelle au sujet du site pour {row['name']} — c'est un bon moment ?") if lang == "fr" else
                            (f"Hi, this is {brand['sender_name']}'s AI assistant from {brand['name']}. You asked us to call about "
                             f"the website for {row['name']} — is now a good time?"),
            "model": {"provider": "anthropic", "model": cfg["ai"]["model"], "messages": [{"role": "system", "content":
                      SCRIPT[lang].format(sender=brand["sender_name"], brand=brand["name"], name=row["name"],
                                          url=row["site_url"], plans=plans_text(cfg, lang, row["currency"]))}]},
            "transcriber": {"provider": "deepgram", "language": lang},
            "endCallFunctionEnabled": True,
            "maxDurationSeconds": 600,
            "analysisPlan": {"summaryPrompt": "Summarise the call in 2 lines and state the outcome: won / thinking / not interested."},
        }
        if cfg.dry_run:
            call_id = "dry-run-call"
        else:
            r = requests.post(f"{VAPI}/call", headers=_h(), timeout=30, json={
                "phoneNumberId": Config.secret("VAPI_PHONE_NUMBER_ID"),
                "customer": {"number": number, "name": row["name"]},
                "assistant": assistant,
            })
            if not r.ok:
                db.log(row["id"], "call_error", r.text)
                continue
            call_id = r.json()["id"]
        db.update(row["id"], called_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        db.log(row["id"], "call_started", json.dumps({"call_id": call_id, "number": number}))
        log(f"  ☎ calling {row['name']} at {number}")
        n += 1
    return n


def sync(cfg: Config, db: DB, log=print) -> int:
    """Pull summaries of finished calls into the event log; outcome 'won' flags the lead for a human to close."""
    if not cfg["voice"]["enabled"] or cfg.dry_run:
        return 0
    n = 0
    for ev in db.conn.execute("SELECT * FROM events WHERE kind='call_started'").fetchall():
        call_id = json.loads(ev["detail"])["call_id"]
        if db.conn.execute("SELECT 1 FROM events WHERE kind='call_done' AND detail LIKE ?", (f"%{call_id}%",)).fetchone():
            continue
        r = requests.get(f"{VAPI}/call/{call_id}", headers=_h(), timeout=30)
        if not r.ok or r.json().get("status") != "ended":
            continue
        summary = (r.json().get("analysis") or {}).get("summary", "")
        db.log(ev["prospect_id"], "call_done", json.dumps({"call_id": call_id, "summary": summary}))
        if "won" in summary.lower():
            db.update(ev["prospect_id"], status="needs_human")
        log(f"  ☎ call summary saved for #{ev['prospect_id']}")
        n += 1
    return n
