"""Claude API client (plain HTTPS, no SDK) + a deterministic mock for DRY_RUN."""
import json
import re

import requests

from .config import Config

API = "https://api.anthropic.com/v1/messages"


class LLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.model = cfg["ai"]["model"]
        self.mock = cfg.dry_run or not Config.secret("ANTHROPIC_API_KEY", required=False)

    def ask(self, system: str, prompt: str, *, web_search=False, max_tokens=2500, mock=None) -> str:
        if self.mock:
            return mock() if callable(mock) else (mock or "{}")
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if web_search:
            body["tools"] = [{
                "type": self.cfg["ai"]["web_search_tool"],
                "name": "web_search",
                "max_uses": self.cfg["ai"]["max_searches_per_lead"],
            }]
        r = requests.post(API, json=body, timeout=180, headers={
            "x-api-key": Config.secret("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        })
        r.raise_for_status()
        blocks = r.json().get("content", [])
        return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    def ask_json(self, system: str, prompt: str, **kw) -> dict:
        text = self.ask(system + "\n\nRespond with ONE JSON object only. No prose, no code fences.", prompt, **kw)
        return parse_json(text)


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.S)  # last resort: outermost object
        if m:
            return json.loads(m.group(0))
        raise
