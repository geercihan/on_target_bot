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
    try:
        with open(SENT_LOG_FILE, "r") as f:
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

# === Extract total shots stats ===
def extract_total_shots(stats):
    total_on, total_off = 0, 0
    for team_stats in stats:
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "Shots on Goal" and isinstance(stat.get("value"), int):
                total_on += stat["value"]
            if stat.get("type") == "Shots off Goal" and isinstance(stat.get("value"), int):
                total_off += stat["value"]
    return total_on, total_off

# === Send Telegram message ===
def send_telegram_alert(fixture, minute, on_target, off_target, home_rank, away_rank):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    round_ = fixture["league"].get("round", "N/A")
    time_str = get_local_time()

    message = f"📊 <b>{home} vs {away}</b>\n"
    message += f"🏆 <b>{league}</b>\n"
    message += f"🔁 Round: <b>{round_}</b>\n"
    if home_rank: message += f"📈 {home} Rank: <b>{home_rank}</b>\n"
    if away_rank: message += f"📈 {away} Rank: <b>{away_rank}</b>\n"
    message += f"\n⏱ Minute: <b>{minute}</b>\n"
    message += f"🎯 On Target: <b>{on_target}</b>\n"
    message += f"🚀 Off Target: <b>{off_target}</b>\n"
    message += f"\n🕒 Alert Time: <b>{time_str}</b>"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    res = requests.post(url, data=payload)
    if res.ok:
        print(f"[ALERT ✅] {home} vs {away} — {minute}′")
    else:
        print(f"[ERROR] Failed to send alert: {res.text}")

# === Main Bot Logic ===
def main():
    sent_alerts = load_sent_alerts()
    live_matches = fetch_live_matches()
    print(f"[INFO] Total live matches: {len(live_matches)}")

    for match in live_matches:
        fixture_id = match["fixture"]["id"]
        minute = match["fixture"]["status"]["elapsed"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]

        print(f"\n[CHECK] {home} vs {away} — Min: {minute}")

        if not minute or minute > 15:
            print("[SKIP] Match beyond 15 minutes.")
            continue
        if str(fixture_id) in sent_alerts:
            print("[SKIP] Already alerted.")
            continue

        stats = match.get("statistics", [])
        on_target, off_target = extract_total_shots(stats)
        total_shots = on_target + off_target
        print(f"[STATS] 🎯 On: {on_target} | 🚀 Off: {off_target} | Total: {total_shots}")

        if total_shots >= 3 and on_target >= 1:
            home_rank = match["teams"]["home"].get("league", {}).get("position")
            away_rank = match["teams"]["away"].get("league", {}).get("position")
            send_telegram_alert(match, minute, on_target, off_target, home_rank, away_rank)
            sent_alerts.add(str(fixture_id))
        else:
            print("[SKIP] Conditions not met.")

    save_sent_alerts(sent_alerts)
    print(f"\n[DONE] ✅ Checked {len(live_matches)} matches.")

if __name__ == "__main__":
    main()
