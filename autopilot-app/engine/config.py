"""Paths + config.

RES  = read-only bundled resources (templates, fixtures). Inside the .exe this is PyInstaller's bundle dir.
HOME = writable user data (config.yaml, .env, database, generated sites, outbox).
       Desktop app: %APPDATA%\\Autopilot.  CLI: the project folder (or $AUTOPILOT_HOME).
"""
import os
import shutil
import sys
from pathlib import Path

import yaml

RES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ROOT = RES  # backwards compatibility


def home() -> Path:
    h = Path(os.environ.get("AUTOPILOT_HOME") or RES)
    h.mkdir(parents=True, exist_ok=True)
    return h


def _load_env(path: Path, override=False):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if override:
            os.environ[k.strip()] = v.strip()
        else:
            os.environ.setdefault(k.strip(), v.strip())


class Config:
    def __init__(self, path: str | None = None):
        h = home()
        _load_env(h / ".env", override=True)
        p = Path(path) if path else h / "config.yaml"
        if not p.exists():
            shutil.copy(RES / "config.example.yaml", p)
        self.path = p
        self.data = yaml.safe_load(p.read_text(encoding="utf-8"))
        self.dry_run = os.environ.get("DRY_RUN", "0") == "1" or bool(self.data.get("test_mode"))

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def save(self):
        self.path.write_text(yaml.safe_dump(self.data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    @staticmethod
    def secret(name: str, required: bool = True) -> str:
        v = os.environ.get(name, "")
        if required and not v:
            raise RuntimeError(f"Missing {name} — add it in Settings → Connections")
        return v

    def markets(self, only_enabled=True):
        return [m for m in self.data["markets"] if m.get("enabled") or not only_enabled]

    def market(self, market_id):
        for m in self.data["markets"]:
            if m["id"] == market_id:
                return m
        raise KeyError(market_id)
