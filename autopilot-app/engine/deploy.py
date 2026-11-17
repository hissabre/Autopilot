"""Step 4 — publish each demo site on its own URL (Netlify), and take unclaimed ones down later."""
import io
import os
import zipfile
from datetime import datetime, timedelta, timezone

import requests

from .config import Config
from .db import DB
from .sitegen import SITES_DIR

NETLIFY = "https://api.netlify.com/api/v1"


def _h():
    return {"Authorization": f"Bearer {Config.secret('NETLIFY_TOKEN')}"}


def _zip(folder):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(folder))
    return buf.getvalue()


def publish(slug: str, cfg: Config, site_id: str | None = None) -> tuple[str, str]:
    folder = SITES_DIR / slug
    if cfg.dry_run or cfg["deploy"]["provider"] == "local":
        base = os.environ.get("AUTOPILOT_LOCAL_BASE", "http://localhost:8080")
        return f"{base}/sites/{slug}/", "local"
    if not site_id:
        r = requests.post(f"{NETLIFY}/sites", json={"name": slug}, headers=_h(), timeout=30)
        if r.status_code == 422:  # name taken — let Netlify pick a suffix
            r = requests.post(f"{NETLIFY}/sites", json={"name": f"{slug}-x"}, headers=_h(), timeout=30)
        r.raise_for_status()
        site = r.json()
        site_id = site["id"]
    r = requests.post(f"{NETLIFY}/sites/{site_id}/deploys", data=_zip(folder),
                      headers={**_h(), "Content-Type": "application/zip"}, timeout=120)
    r.raise_for_status()
    d = r.json()
    url = d.get("ssl_url") or d.get("url") or f"https://{slug}.netlify.app"
    return url.rstrip("/") + "/", site_id


def unpublish(site_id: str, cfg: Config):
    if cfg.dry_run or site_id == "local":
        return
    requests.delete(f"{NETLIFY}/sites/{site_id}", headers=_h(), timeout=30).raise_for_status()


def run(cfg: Config, db: DB, log=print) -> int:
    n = 0
    for row in db.by_status("site_built", limit=cfg["limits"]["max_sites_per_run"]):
        try:
            url, site_id = publish(row["site_slug"], cfg, row["site_deploy_id"])
        except Exception as e:  # noqa: BLE001
            db.log(row["id"], "deploy_error", str(e))
            log(f"  ! {row['name']}: deploy failed ({e})")
            continue
        db.update(row["id"], status="deployed", site_url=url, site_deploy_id=site_id)
        db.log(row["id"], "deployed", url)
        log(f"  ✓ {row['name']} → {url}")
        n += 1
    return n


def takedown_stale(cfg: Config, db: DB, log=print) -> int:
    days = cfg["limits"]["takedown_demo_after_days"]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    for row in db.by_status("contacted", "followed_up", "not_interested", "unsubscribed", "bounced", "lost"):
        if not row["site_deploy_id"]:
            continue
        terminal = row["status"] in ("not_interested", "unsubscribed", "bounced")
        stale = row["contacted_at"] and datetime.fromisoformat(row["contacted_at"]) < cutoff
        if not (terminal or stale):
            continue
        try:
            unpublish(row["site_deploy_id"], cfg)
        except Exception as e:  # noqa: BLE001
            db.log(row["id"], "takedown_error", str(e))
            continue
        new_status = row["status"] if row["status"] in ("unsubscribed", "not_interested", "bounced") else "lost"
        db.update(row["id"], status=new_status, site_deploy_id=None, site_url=None)
        db.log(row["id"], "taken_down", "")
        log(f"  - took down demo for {row['name']}")
        n += 1
    return n
