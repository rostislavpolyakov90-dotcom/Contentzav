#!/usr/bin/env python3
"""Тянет свои посты из Threads API + их insights, дописывает снимки в data/metrics.csv."""
import csv, os, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://graph.threads.net/v1.0"
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "data" / "metrics.csv"
POSTS = ROOT / "data" / "posts.csv"

POST_FIELDS = "id,media_type,permalink,text,timestamp,is_quote_post"
METRIC_NAMES = "views,likes,replies,reposts,quotes"

METRICS_HEADER = ["snapshot_at", "post_id", "age_hours", "views", "likes",
                  "replies", "reposts", "quotes", "er", "reply_rate"]
POSTS_HEADER = ["post_id", "published_at", "permalink", "text_head", "rubric",
                "hook_type", "format", "length", "has_question", "cta_type",
                "experiment_id", "source"]


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get(url, params, retries=3):
    for attempt in range(retries):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 429:
            wait = 60 * (attempt + 1)
            print(f"  лимит запросов, жду {wait}с", file=sys.stderr)
            time.sleep(wait)
            continue
        if not r.ok:
            raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("Исчерпаны попытки из-за лимита запросов")


def fetch_posts(limit):
    data = get(f"{BASE}/me/threads", {
        "fields": POST_FIELDS, "limit": limit, "access_token": TOKEN})
    return data.get("data", [])


def fetch_insights(post_id):
    data = get(f"{BASE}/{post_id}/insights", {
        "metric": METRIC_NAMES, "access_token": TOKEN})
    out = {}
    for item in data.get("data", []):
        name = item.get("name")
        vals = item.get("values") or [{}]
        out[name] = vals[0].get("value", 0)
    return out


def ensure(path, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)


def known_post_ids():
    if not POSTS.exists():
        return set()
    with POSTS.open(encoding="utf-8") as f:
        return {row["post_id"] for row in csv.DictReader(f)}


def main(limit=50):
    load_env()
    if not os.getenv("THREADS_ACCESS_TOKEN"):
        sys.exit("Нет THREADS_ACCESS_TOKEN в .env")
    globals()["TOKEN"] = os.getenv("THREADS_ACCESS_TOKEN")

    ensure(METRICS, METRICS_HEADER)
    ensure(POSTS, POSTS_HEADER)
    seen = known_post_ids()
    now = datetime.now(timezone.utc)

    posts = fetch_posts(limit)
    print(f"Получено постов: {len(posts)}")

    new_rows, metric_rows = [], []
    for p in posts:
        pid = p["id"]
        published = p.get("timestamp", "")
        try:
            pub_dt = datetime.fromisoformat(published.replace("+0000", "+00:00"))
            age_h = round((now - pub_dt).total_seconds() / 3600, 1)
        except Exception:
            age_h = ""

        try:
            ins = fetch_insights(pid)
        except RuntimeError as e:
            print(f"  insights недоступны для {pid}: {e}", file=sys.stderr)
            continue

        views = ins.get("views", 0) or 0
        eng = sum(ins.get(k, 0) or 0 for k in ("likes", "replies", "reposts", "quotes"))
        er = round(eng / views, 4) if views else 0
        rr = round((ins.get("replies", 0) or 0) / views, 4) if views else 0

        metric_rows.append([now.isoformat(timespec="seconds"), pid, age_h,
                            views, ins.get("likes", 0), ins.get("replies", 0),
                            ins.get("reposts", 0), ins.get("quotes", 0), er, rr])

        if pid not in seen:
            text = (p.get("text") or "").replace("\n", " ")
            new_rows.append([pid, published, p.get("permalink", ""), text[:60],
                             "", "", p.get("media_type", ""), len(p.get("text") or ""),
                             "", "", "", "auto"])
        time.sleep(0.4)  # бережём лимиты

    with METRICS.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(metric_rows)
    with POSTS.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(new_rows)

    print(f"Снимков метрик добавлено: {len(metric_rows)}")
    print(f"Новых постов в реестре: {len(new_rows)}")
    if new_rows:
        print("Требуют заполнения атрибутов (rubric/hook_type/…):")
        for r in new_rows:
            print(f"  {r[0]}  {r[3]}")


if __name__ == "__main__":
    lim = 50
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    main(lim)
