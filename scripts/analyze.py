#!/usr/bin/env python3
"""Считает срезы по data/*.csv: медианы ER по рубрикам, хукам, длине, дню недели."""
import csv, statistics, sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "data" / "metrics.csv"
POSTS = ROOT / "data" / "posts.csv"

AGE_BUCKETS = [(20, 30, "T+24h"), (60, 90, "T+72h"), (150, 200, "T+7d")]


def read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def bucket_of(age):
    try:
        a = float(age)
    except (TypeError, ValueError):
        return None
    for lo, hi, name in AGE_BUCKETS:
        if lo <= a <= hi:
            return name
    return None


def med(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 4) if vals else None


def main(weeks=8):
    metrics, posts = read(METRICS), read(POSTS)
    if not metrics:
        print("Нет данных в metrics.csv"); return

    meta = {p["post_id"]: p for p in posts}
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=weeks)

    # для каждого поста берём по одному снимку на возрастной бакет
    chosen = {}
    for m in metrics:
        b = bucket_of(m.get("age_hours"))
        if not b:
            continue
        key = (m["post_id"], b)
        prev = chosen.get(key)
        if not prev or m["snapshot_at"] > prev["snapshot_at"]:
            chosen[key] = m

    rows = []
    for (pid, b), m in chosen.items():
        p = meta.get(pid, {})
        pub = p.get("published_at", "")
        try:
            if pub and datetime.fromisoformat(pub.replace("+0000", "+00:00")) < cutoff:
                continue
        except Exception:
            pass
        rows.append({
            "post_id": pid, "bucket": b,
            "er": float(m["er"] or 0), "views": int(m["views"] or 0),
            "replies": int(m["replies"] or 0),
            "rubric": p.get("rubric") or "—",
            "hook_type": p.get("hook_type") or "—",
            "length": int(p.get("length") or 0),
            "has_question": p.get("has_question") or "—",
            "dow": (datetime.fromisoformat(pub.replace("+0000", "+00:00")).strftime("%a")
                    if pub else "—"),
        })

    focus = [r for r in rows if r["bucket"] == "T+72h"] or rows
    print(f"\n=== Выборка: {len(focus)} постов (бакет {focus[0]['bucket'] if focus else '—'}) ===")
    print(f"Медиана ER: {med([r['er'] for r in focus])}")
    print(f"Медиана просмотров: {med([float(r['views']) for r in focus])}")

    def cut(field, labeler=lambda r, f: r[f]):
        g = defaultdict(list)
        for r in focus:
            g[labeler(r, field)].append(r["er"])
        print(f"\n--- Срез: {field} ---")
        for k, v in sorted(g.items(), key=lambda kv: -(med(kv[1]) or 0)):
            flag = "  ⚠ мало данных" if len(v) < 8 else ""
            print(f"  {str(k):24} n={len(v):3}  медиана ER={med(v)}{flag}")

    cut("rubric"); cut("hook_type"); cut("has_question"); cut("dow")
    cut("length", lambda r, f: "<250" if r[f] < 250 else ("250-350" if r[f] <= 350 else ">350"))


if __name__ == "__main__":
    w = 8
    if "--weeks" in sys.argv:
        w = int(sys.argv[sys.argv.index("--weeks") + 1])
    main(w)
