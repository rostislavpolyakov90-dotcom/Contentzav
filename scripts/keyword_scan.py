#!/usr/bin/env python3
"""Threads keyword_search по ключам ниши → trends/raw/<дата>/threads.json"""
import json, os, sys, time
from datetime import datetime
from pathlib import Path
import requests

BASE = "https://graph.threads.net/v1.0"
ROOT = Path(__file__).resolve().parent.parent
KEYWORDS_FILE = ROOT / "trends" / "keywords.txt"
FIELDS = "id,text,media_type,permalink,timestamp,username"


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def search(q, token, mode=None):
    params = {"q": q, "fields": FIELDS, "access_token": token}
    if mode:
        params["search_mode"] = mode
    r = requests.get(f"{BASE}/keyword_search", params=params, timeout=30)
    if not r.ok:
        print(f"  [{q}] ошибка {r.status_code}: {r.text[:200]}", file=sys.stderr)
        return []
    return r.json().get("data", [])


def main():
    load_env()
    token = os.getenv("THREADS_ACCESS_TOKEN")
    if not token:
        sys.exit("Нет THREADS_ACCESS_TOKEN")
    if not KEYWORDS_FILE.exists():
        sys.exit(f"Создайте {KEYWORDS_FILE} — по одному ключу в строке")

    # Комментарий — строка "# что-то" (# и пробел). Тег без пробела ("#психолог") — ключевое слово.
    keywords = []
    for raw in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line == "#" or line.startswith("# "):
            continue
        keywords.append(line)

    out_dir = ROOT / "trends" / "raw" / datetime.now().strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)

    result = {}
    for kw in keywords:
        mode = "TAG" if kw.startswith("#") else None
        items = search(kw, token, mode)
        result[kw] = items
        print(f"{kw}: {len(items)}")
        time.sleep(1)

    (out_dir / "threads.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {out_dir/'threads.json'}")


if __name__ == "__main__":
    main()
