#!/usr/bin/env python3
"""Обмен короткого токена на долгий и обновление долгого токена."""
import argparse, os, sys
import requests

BASE = "https://graph.threads.net"

def exchange(short_token: str, app_secret: str) -> dict:
    r = requests.get(f"{BASE}/access_token", params={
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short_token,
    }, timeout=30)
    r.raise_for_status()
    return r.json()

def refresh(long_token: str) -> dict:
    r = requests.get(f"{BASE}/refresh_access_token", params={
        "grant_type": "th_refresh_token",
        "access_token": long_token,
    }, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["exchange", "refresh"])
    p.add_argument("--token", required=True)
    p.add_argument("--secret", default=os.getenv("THREADS_APP_SECRET"))
    a = p.parse_args()

    if a.mode == "exchange":
        if not a.secret:
            sys.exit("Нужен --secret или THREADS_APP_SECRET в окружении")
        data = exchange(a.token, a.secret)
    else:
        data = refresh(a.token)

    print("Токен:", data.get("access_token", "")[:20] + "…")
    print("Живёт секунд:", data.get("expires_in"))
    print("\nПоложите в .env строкой:\nTHREADS_ACCESS_TOKEN=" + data.get("access_token", ""))
