"""Step 6 — read replies, classify them, act: answer, send plans, schedule a call, unsubscribe, flag a human."""
import email
import imaplib
import json
import re
from email import policy
from email.utils import parseaddr

from .config import Config, home
from .db import DB
from .llm import LLM
from .mailer import Mailer

SYSTEM = "You triage replies to a web studio's outreach emails. Be precise."
PROMPT = """Reply from {name} about the free demo website we built for them.
---
{body}
---
Return JSON:
{{"intent": "interested|question|not_interested|unsubscribe|auto_reply|other",
  "wants_call": true/false,
  "phone": "phone number they gave, or null",
  "summary": "one line"}}"""

UNSUB_WORDS = re.compile(r"(\bunsubscribe\b|\bremove me\b|^\s*stop\s*\.?\s*$|d[ée]sinscri|\bne plus m|\bretirez[- ]moi)",
                         re.I | re.M)


def _body(msg) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    text = part.get_content() if part else ""
    if part and part.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", " ", text)
    # strip quoted history
    text = re.split(r"\n(?:On .+wrote:|Le .+a écrit\s?:|-{2,}\s*Original Message)", text)[0]
    return "\n".join(l for l in text.splitlines() if not l.startswith(">")).strip()


def fetch(cfg: Config):
    if cfg.dry_run:
        d = home() / "test-inbox"
        for f in sorted(d.glob("*.eml")) if d.exists() else []:
            yield email.message_from_bytes(f.read_bytes(), policy=policy.default)
            f.rename(f.with_suffix(".done"))
        return
    if cfg["inbox"]["provider"] == "none":
        return
    ic = cfg["inbox"]
    M = imaplib.IMAP4_SSL(ic["host"], ic["port"])
    M.login(Config.secret("IMAP_USER"), Config.secret("IMAP_PASSWORD"))
    M.select(ic["folder"])
    _, ids = M.search(None, "UNSEEN")
    for i in ids[0].split():
        _, data = M.fetch(i, "(RFC822)")
        yield email.message_from_bytes(data[0][1], policy=policy.default)
        M.store(i, "+FLAGS", "\\Seen")
    M.logout()


def match(db: DB, msg):
    refs = " ".join(filter(None, [msg.get("In-Reply-To", ""), msg.get("References", "")]))
    for mid in re.findall(r"<[^>]+>", refs):
        row = db.by_message_id(mid)
        if row:
            return row
    return db.by_email(parseaddr(msg.get("From", ""))[1])


def handle_bounce(db: DB, msg, log):
    raw = msg.as_string()
    for addr in set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", raw)):
        row = db.by_email(addr)
        if row:
            db.suppress(addr, "bounce")
            db.update(row["id"], status="bounced")
            db.log(row["id"], "bounced", "")
            log(f"  × bounce: {row['name']}")
            return


def run(cfg: Config, db: DB, llm: LLM, mailer: Mailer, log=print) -> int:
    n = 0
    for msg in fetch(cfg):
        sender = parseaddr(msg.get("From", ""))[1].lower()
        if "mailer-daemon" in sender or "postmaster" in sender:
            handle_bounce(db, msg, log)
            continue
        row = match(db, msg)
        if not row:
            continue
        body = _body(msg)
        db.log(row["id"], "reply_in", body)

        # Hard rule first: any opt-out wording wins, no AI needed.
        if UNSUB_WORDS.search(body) and len(body) < 400:
            intent = {"intent": "unsubscribe", "wants_call": False, "phone": None, "summary": "opt-out"}
        else:
            intent = llm.ask_json(SYSTEM, PROMPT.format(name=row["name"], body=body[:3000]), mock=lambda: json.dumps({
                "intent": "interested" if re.search(r"\b(yes|oui|interest|intéress|love|like|combien|price|how much)\b", body, re.I) else "other",
                "wants_call": bool(re.search(r"\b(call|appel)", body, re.I)),
                "phone": (re.search(r"\+?\d[\d\s().-]{7,}\d", body) or [None])[0],
                "summary": body[:80]}))
        kind = intent.get("intent", "other")
        log(f"  ← {row['name']}: {kind} — {intent.get('summary', '')}")

        if kind == "unsubscribe" or kind == "not_interested":
            db.suppress(row["email"], kind)
            db.update(row["id"], status="unsubscribed" if kind == "unsubscribe" else "not_interested")
            db.log(row["id"], kind, "")
            n += 1
            continue
        if kind == "auto_reply":
            continue

        fields = {}
        if intent.get("wants_call") or intent.get("phone"):
            fields.update(call_requested=1, call_number=intent.get("phone") or row["phone"])

        if row["auto_replies"] >= cfg["limits"]["max_auto_replies_per_thread"]:
            db.update(row["id"], status="needs_human", **fields)
            db.log(row["id"], "needs_human", "auto-reply limit reached")
            continue
        try:
            out = mailer.reply(row, body, msg.get("Subject", ""), msg.get("Message-ID", row["message_id"]))
        except Exception as e:  # noqa: BLE001
            db.log(row["id"], "reply_error", str(e))
            db.update(row["id"], status="needs_human", **fields)
            continue
        status = "needs_human" if out.get("needs_human") else ("interested" if kind == "interested" else "question")
        db.update(row["id"], status=status, auto_replies=row["auto_replies"] + 1, **fields)
        db.log(row["id"], "reply_out", out["body"])
        n += 1
    return n


SIM = {
    "en": [("interested", "This looks great! How much would it be? You can call me at 604-555-0142 after 2pm."),
           ("question", "Nice work. Can I use my own photos and would I own the domain?"),
           ("unsubscribe", "Please unsubscribe me."),
           ("interested", "Love it. Yes, let's put it on my own domain. What are the next steps?")],
    "fr": [("interested", "C'est très joli ! Combien ça coûte ? Appelez-moi au 76 12 34 56."),
           ("question", "Merci. Est-ce que je peux mettre mes propres photos ?"),
           ("unsubscribe", "Merci de me désinscrire."),
           ("interested", "Oui je suis intéressé, on fait comment ?")],
}


def simulate_replies(cfg: Config, db: DB, chance=0.35):
    """Test mode only: write fake replies into the test inbox so the reply flow can be seen."""
    if not cfg.dry_run:
        return 0
    d = home() / "test-inbox"
    d.mkdir(parents=True, exist_ok=True)
    import random
    n = 0
    for row in db.by_status("contacted", "followed_up"):
        if random.random() > chance:
            continue
        lang = cfg.market(row["market"])["language"]
        _, body = random.choice(SIM.get(lang, SIM["en"]))
        (d / f"sim-{row['id']}-{random.getrandbits(24):x}.eml").write_text(
            f"From: {row['email']}\nTo: {cfg['brand']['reply_to']}\nSubject: Re: website\n"
            f"Message-ID: <sim{random.getrandbits(32)}@test>\nIn-Reply-To: {row['message_id']}\n"
            f"Content-Type: text/plain; charset=utf-8\n\n{body}\n", encoding="utf-8")
        n += 1
    return n
