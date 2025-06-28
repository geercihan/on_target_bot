import os
import json
import requests
from datetime import datetime
import pytz

# === Environment Variables ===
API_KEY = os.getenv("API_KEY", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = pytz.timezone("Africa/Tunis")
SENT_LOG_FILE = "sent_log.json"

# === Load sent alerts from file ===
def load_sent_alerts():
    if not os.path.exists(SENT_LOG_FILE):
        return set()
    with open(SENT_LOG_FILE, "r") as f:
        try:
            return set(json.load(f).get("sent", []))
        except:
            return set()

# === Save updated sent alerts ===
def save_sent_alerts(sent_set):
    with open(SENT_LOG_FILE, "w") as f:
        json.dump({"sent": list(sent_set)}, f)

# === Format current time ===
def get_local_time():
    return datetime.now(TIMEZONE).strftime("%H:%M:%S")

# === Get live matches from API-Football ===
def fetch_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[ERROR] Failed to fetch live matches: {response.status_code}")
        return []
    return response.json().get("response", [])

# === Extract shot stats ===
def extract_shots(stats):
    on, off = 0, 0
    for team in stats:
        shots = team.get("statistics", [])
        for stat in shots:
            if stat.get("type") == "Shots on Goal" and isinstance(stat.get("value"), int):
                on += stat["value"]
            if stat.get("type") == "Shots off Goal" and isinstance(stat.get("value"), int):
                off += stat["value"]
    return on, off

# === Fetch real stats using separate endpoint ===
def get_fixture_stats(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[ERROR] Failed to fetch stats for fixture {fixture_id}: {response.status_code}")
        return 0, 0
    data = response.json().get("response", [])
    return extract_shots(data)

# === Send Telegram message ===
def send_telegram_alert(fixture, minute, on_target, off_target, home_rank, away_rank):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    time_str = get_local_time()

    message = f"📊 <b>{home} vs {away}</b>\n"
    message += f"🏆 <b>{league}</b>\n"
    if home_rank: message += f"📈 {home} Rank: <b>{home_rank}</b>\n"
    if away_rank: message += f"📈 {away} Rank: <b>{away_rank}</b>\n"
    message += f"\n⏱ Minute: <b>{minute}</b>\n"
    message += f"🎯 On Target: <b>{on_target}</b>\n"
    message += f"🚀 Off Target: <b>{off_target}</b>\n"
    message += f"\n🕒 Alert Time: <b>{time_str}</b>"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    response = requests.post(url, data=payload)
    if response.ok:
        print(f"[ALERT] ✅ {home} vs {away} — {minute}′ — Sent")
    else:
        print(f"[ALERT ERROR] ❌ Failed to send message: {response.text}")

# === Main Bot Logic ===
def main():
    sent_alerts = load_sent_alerts()
    live_matches = fetch_live_matches()
    print(f"[INFO] Total live matches fetched: {len(live_matches)}")

    for match in live_matches:
        fixture_id = match["fixture"]["id"]
        minute = match["fixture"]["status"]["elapsed"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]

        print(f"[CHECK] {home} vs {away} — Minute: {minute}")

        if not minute or minute > 15:
            print(f"[SKIP] ⏱ Match beyond minute 15.")
            continue
        if str(fixture_id) in sent_alerts:
            print(f"[SKIP] 🔁 Already alerted.")
            continue

        on_target, off_target = get_fixture_stats(fixture_id)

        print(f"[STATS] 🎯 On: {on_target} | 🚀 Off: {off_target}")

        if on_target >= 1 and off_target >= 2:
            home_rank = match["teams"]["home"].get("league", {}).get("position")
            away_rank = match["teams"]["away"].get("league", {}).get("position")
            send_telegram_alert(match, minute, on_target, off_target, home_rank, away_rank)
            sent_alerts.add(str(fixture_id))
        else:
            print(f"[SKIP] ❌ Conditions not met.")

    save_sent_alerts(sent_alerts)
    print(f"[DONE] Processed {len(live_matches)} matches.")

if __name__ == "__main__":
    main()
