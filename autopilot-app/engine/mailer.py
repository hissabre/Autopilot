"""Step 5 — personalised outreach, one follow-up, plan offers and replies. Compliance footer on every email."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from zoneinfo import ZoneInfo

import requests

from .config import Config, home
from .db import DB
from .llm import LLM

OUTBOX = home() / "out" / "outbox"

FOOTER = {
    "en": "{brand} · {address}\nYou're receiving this because your business email is publicly listed. "
          "Not interested? Reply \"unsubscribe\" and you'll never hear from us again.{unsub}",
    "fr": "{brand} · {address}\nVous recevez ce message car l'adresse de votre commerce est publique. "
          "Pas intéressé ? Répondez « désinscrire » et nous ne vous écrirons plus.{unsub}",
}

SYSTEM = """You write short cold emails for a tiny web studio that already BUILT a free demo website for a
local business. Tone: human, warm, specific, zero hype, no pressure. Plain text only, no markdown, no emojis.
Never claim things you don't know. Never fake urgency or discounts. Sign with the sender's first name."""

FIRST = """Language: {lang}
Business: {name} ({category}), {city}
Owner first name: {owner}
Google: {rating}★ from {reviews} reviews
Demo website we built for them: {url}
Sender: {sender} from {brand}

Write the first email. Under 110 words. Structure:
- greet (use owner name if known, otherwise the business name)
- one specific line showing we noticed them (their rating/reviews, what they do)
- they don't have a website yet, so we built one for them — link
- it's theirs if they like it; we can host and keep it updated for a small monthly fee; no obligation
- soft question as the call to action (e.g. "Want me to put it on your own domain?")
Return JSON: {{"subject": "max 7 words, lowercase style, no clickbait", "body": "..."}}"""

FOLLOWUP = """Language: {lang}
Business: {name}. We emailed {days} days ago with a free demo site: {url}
Write a 2-3 sentence friendly follow-up. No guilt, no pressure. Mention the link stays up for a few more weeks.
Return JSON: {{"body": "..."}}"""

KB = """Facts you may use when answering (do not go beyond them):
- The demo site is free to look at. If they want it, we put it on their own domain (we can register one; they own it).
- Plans: {plans}
- Setup in 48h after they say yes. Changes to text/photos usually within 2 business days.
- Cancel any time, no contract. If they leave, they keep their domain and we send them the site files.
- We can add photos they send us, a booking/order form, WhatsApp button, Google Business Profile help.
- Payment: {payment}
- Booking a call: {booking}"""

REPLY = """Language: {lang}
Business: {name}. Their demo: {url}
Thread so far (latest last):
{thread}

{kb}

Write our reply. Under 140 words. If they asked something not covered by the facts, say you'll check and get back
to them, and set needs_human true. If they're interested, present the plans briefly with prices and how to start,
and offer a quick call ("reply with the best number and time"). Sign as {sender}.
Return JSON: {{"body": "...", "needs_human": true/false}}"""


def plans_text(cfg, lang, currency):
    out = []
    for p in cfg["plans"]:
        pr = p["price"].get(currency) or next(iter(p["price"].values()))
        setup = f"{pr['setup']:,} {currency} setup + " if pr["setup"] else ""
        out.append(f"{p['name'][lang]}: {setup}{pr['monthly']:,} {currency}/{'mois' if lang == 'fr' else 'month'} "
                   f"({'; '.join(p['features'][lang])})")
    return " | ".join(out)


def payment_text(cfg, currency):
    links = [f"{p['id']}: {p['payment_link'].get(currency)}" for p in cfg["plans"] if p["payment_link"].get(currency)]
    return ", ".join(links) or "we send an invoice once they confirm"


class Mailer:
    def __init__(self, cfg: Config, db: DB, llm: LLM):
        self.cfg, self.db, self.llm = cfg, db, llm
        self.provider = "outbox" if cfg.dry_run else cfg["email"]["provider"]

    # ── limits ──
    def daily_cap(self):
        first = self.db.meta_get("first_send_day")
        lim = self.cfg["limits"]
        if not first:
            return lim["warmup_start"]
        days = (datetime.now().date() - datetime.fromisoformat(first).date()).days
        return min(lim["max_emails_per_day"], lim["warmup_start"] + lim["warmup_step"] * days)

    def can_send_now(self, market) -> bool:
        if self.cfg.dry_run:
            return True
        local = datetime.now(ZoneInfo(market["timezone"]))
        start, end = self.cfg["limits"]["send_window_local"]
        return local.weekday() < 5 and start <= local.hour <= end

    def today(self):
        return datetime.now().date().isoformat()  # local calendar day

    def budget_left(self):
        return self.daily_cap() - self.db.sent_today(self.today())

    # ── transport ──
    def send(self, to, subject, body, lang, in_reply_to=None, pid=None) -> str:
        if self.db.is_suppressed(to):
            raise RuntimeError("suppressed")
        b = self.cfg["brand"]
        unsub = f"\n{b['unsubscribe_base_url']}?e={to}" if b.get("unsubscribe_base_url") else ""
        text = body.strip() + "\n\n—\n" + FOOTER.get(lang, FOOTER["en"]).format(
            brand=b["name"], address=b["postal_address"], unsub=unsub)
        domain = b["sender_email"].split("@")[1]
        mid = f"<{uuid.uuid4().hex}@{domain}>"
        headers = {
            "Message-ID": mid,
            "List-Unsubscribe": f"<mailto:{b['reply_to']}?subject=unsubscribe>" + (f", <{unsub.strip()}>" if unsub else ""),
        }
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
            headers["References"] = in_reply_to

        if self.provider == "outbox":
            OUTBOX.mkdir(parents=True, exist_ok=True)
            m = EmailMessage()
            m["From"] = formataddr((f"{b['sender_name']} · {b['name']}", b["sender_email"]))
            m["To"], m["Subject"], m["Reply-To"] = to, subject, b["reply_to"]
            for k, v in headers.items():
                m[k] = v
            m.set_content(text)
            (OUTBOX / f"{datetime.now():%Y%m%d-%H%M%S}-{pid}-{uuid.uuid4().hex[:6]}.eml").write_bytes(bytes(m))
        else:
            r = requests.post("https://api.resend.com/emails", timeout=30, headers={
                "Authorization": f"Bearer {Config.secret('RESEND_API_KEY')}"}, json={
                "from": formataddr((f"{b['sender_name']} · {b['name']}", b["sender_email"])),
                "to": [to], "subject": subject, "text": text, "reply_to": b["reply_to"], "headers": headers,
            })
            r.raise_for_status()
        self.db.bump_sent(self.today())
        if not self.db.meta_get("first_send_day"):
            self.db.meta_set("first_send_day", self.today())
        return mid

    # ── flows ──
    def first_touch(self, log=print) -> int:
        n = 0
        for row in self.db.by_status("deployed", limit=200):
            if self.budget_left() <= 0:
                log("  · daily send cap reached")
                break
            market = self.cfg.market(row["market"])
            if not self.can_send_now(market):
                continue
            lang = market["language"]
            city = market["city"].split(",")[0]
            b = self.cfg["brand"]
            fallback = {
                "subject": f"un site pour {row['name']}" if lang == "fr" else f"a website for {row['name']}",
                "body": (f"Bonjour {row['owner_name'] or row['name']},\n\nVos {row['reviews']} avis Google "
                         f"({row['rating']}★) parlent pour vous, mais vous n'avez pas encore de site. Nous en avons "
                         f"créé un pour vous : {row['site_url']}\n\nS'il vous plaît, il est à vous. On peut l'héberger "
                         f"et le tenir à jour pour un petit montant mensuel, sans engagement.\n\nOn le met sur votre "
                         f"propre nom de domaine ?\n\n{b['sender_name']}") if lang == "fr" else
                        (f"Hi {row['owner_name'] or row['name']},\n\n{row['reviews']} Google reviews at {row['rating']}★ is "
                         f"impressive, but I couldn't find a website for you, so I built one: {row['site_url']}\n\n"
                         f"If you like it, it's yours. We can host it and keep it updated for a small monthly fee, "
                         f"no contract.\n\nWant me to put it on your own domain?\n\n{b['sender_name']}"),
            }
            try:
                msg = self.llm.ask_json(SYSTEM, FIRST.format(
                    lang=lang, name=row["name"], category=row["category"], city=city,
                    owner=row["owner_name"] or "unknown", rating=row["rating"], reviews=row["reviews"],
                    url=row["site_url"], sender=b["sender_name"], brand=b["name"]),
                    mock=lambda: json.dumps(fallback))
                mid = self.send(row["email"], msg["subject"], msg["body"], lang, pid=row["id"])
            except Exception as e:  # noqa: BLE001
                self.db.log(row["id"], "send_error", str(e))
                log(f"  ! {row['name']}: send failed ({e})")
                continue
            self.db.update(row["id"], status="contacted", message_id=mid,
                           contacted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            self.db.log(row["id"], "emailed", f"{msg['subject']}\n\n{msg['body']}")
            log(f"  ✉ {row['name']} <{row['email']}>")
            n += 1
        return n

    def followups(self, log=print) -> int:
        lim = self.cfg["limits"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=lim["followup_after_days"])
        n = 0
        for row in self.db.by_status("contacted", limit=200):
            if row["followups"] >= lim["max_followups"] or datetime.fromisoformat(row["contacted_at"]) > cutoff:
                continue
            if self.budget_left() <= 0:
                break
            market = self.cfg.market(row["market"])
            if not self.can_send_now(market):
                continue
            lang = market["language"]
            fb = {"body": (f"Petit rappel : votre site de démonstration est toujours en ligne ici {row['site_url']} "
                           f"pour quelques semaines. Dites-moi s'il vous intéresse !") if lang == "fr" else
                          (f"Quick nudge in case this got buried: your demo site is still up at {row['site_url']} "
                           f"for a few more weeks. Happy to tweak anything if you'd like it.")}
            try:
                msg = self.llm.ask_json(SYSTEM, FOLLOWUP.format(lang=lang, name=row["name"],
                                        days=lim["followup_after_days"], url=row["site_url"]),
                                        mock=lambda: json.dumps(fb))
                subj = ("Re: un site pour " if lang == "fr" else "Re: a website for ") + row["name"]
                self.send(row["email"], subj, msg["body"] + f"\n\n{self.cfg['brand']['sender_name']}", lang,
                          in_reply_to=row["message_id"], pid=row["id"])
            except Exception as e:  # noqa: BLE001
                self.db.log(row["id"], "send_error", str(e))
                continue
            self.db.update(row["id"], status="followed_up", followups=row["followups"] + 1,
                           last_followup_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            self.db.log(row["id"], "followed_up", msg["body"])
            log(f"  ↻ follow-up → {row['name']}")
            n += 1
        return n

    def reply(self, row, thread: str, subject: str, in_reply_to: str) -> dict:
        market = self.cfg.market(row["market"])
        lang, cur = market["language"], row["currency"] or market["currency"]
        b = self.cfg["brand"]
        kb = KB.format(plans=plans_text(self.cfg, lang, cur), payment=payment_text(self.cfg, cur),
                       booking=b.get("booking_url") or "they can reply with a number and time")
        fb = {"body": (f"Merci ! Voici nos formules : {plans_text(self.cfg, lang, cur)}. "
                       f"Si vous préférez en parler, répondez avec le meilleur numéro et horaire.\n\n{b['sender_name']}")
                      if lang == "fr" else
                      (f"Great to hear! Here are the options: {plans_text(self.cfg, lang, cur)}. "
                       f"Happy to hop on a quick call too, just reply with the best number and time.\n\n{b['sender_name']}"),
              "needs_human": False}
        out = self.llm.ask_json(SYSTEM, REPLY.format(lang=lang, name=row["name"], url=row["site_url"],
                                thread=thread[-4000:], kb=kb, sender=b["sender_name"]),
                                mock=lambda: json.dumps(fb))
        subj = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        self.send(row["email"], subj, out["body"], lang, in_reply_to=in_reply_to, pid=row["id"])
        return out
