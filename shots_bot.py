import os
import requests
from datetime import datetime
import pytz
import json

# === Configuration ===
API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = pytz.timezone("Africa/Tunis")
SENT_FILE = "sent.json"

# === Load previously sent alerts ===
def load_sent_alerts():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return set(data.get("sent", []))
        except Exception:
            return set()

# === Save updated sent alerts ===
def save_sent_alerts(sent_alerts):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent": list(sent_alerts)}, f, ensure_ascii=False, indent=2)

# === Fetch all live matches ===
def get_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] API request failed: {response.status_code}")
            return []
        return response.json().get("response", [])
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return []

# === Check alert conditions ===
def should_alert(stats):
    try:
        on_target = stats["shots"]["on"]["total"] or 0
        off_target = stats["shots"]["off"]["total"] or 0
        return on_target >= 1 and off_target >= 2, on_target, off_target
    except:
        return False, 0, 0

# === Format local time ===
def get_local_time():
    return datetime.now(TIMEZONE).strftime("%H:%M:%S")

# === Extract team rankings if available ===
def get_team_rankings(fixture):
    home_rank = fixture.get("teams", {}).get("home", {}).get("league", {}).get("position")
    away_rank = fixture.get("teams", {}).get("away", {}).get("league", {}).get("position")
    return home_rank, away_rank

# === Send Telegram message ===
def send_telegram_alert(fixture, minute, on_target, off_target, home_rank, away_rank):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    time_str = get_local_time()

    message = (
        f"📊 <b>{home} vs {away}</b>\n"
        f"🏆 <b>{league}</b>\n"
    )
    if home_rank and away_rank:
        message += (
            f"📈 {home} Rank: <b>{home_rank}</b>\n"
            f"📈 {away} Rank: <b>{away_rank}</b>\n"
        )
    message += (
        f"\n⏱ Minute: <b>{minute}</b>\n"
        f"🎯 On Target: <b>{on_target}</b>\n"
        f"🚀 Off Target: <b>{off_target}</b>\n"
        f"\n🕒 Alert Time: <b>{time_str}</b>"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, data=payload, timeout=10)
        print(f"[ALERT SENT] {home} vs {away} ✅")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")

# === Main logic ===
def main():
    sent_alerts = load_sent_alerts()
    matches = get_live_matches()
    print(f"[INFO] Live matches fetched: {len(matches)}")

    for fixture in matches:
        fixture_id = fixture["fixture"]["id"]
        minute = fixture["fixture"]["status"]["elapsed"]
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]

        stats = fixture.get("statistics", [{}])[0]
        should_send, on_target, off_target = should_alert(stats)

        print(f"[CHECK] {home} vs {away} — Min: {minute} — On: {on_target} / Off: {off_target}")

        if not minute or minute > 15:
            print(f"[SKIP] {home} vs {away} — Minute > 15")
            continue

        if not should_send:
            print(f"[SKIP] {home} vs {away} — Conditions not met")
            continue

        if str(fixture_id) in sent_alerts:
            print(f"[SKIP] {home} vs {away} — Already alerted")
            continue

        home_rank, away_rank = get_team_rankings(fixture)
        send_telegram_alert(fixture, minute, on_target, off_target, home_rank, away_rank)
        sent_alerts.add(str(fixture_id))

    save_sent_alerts(sent_alerts)

if __name__ == "__main__":
    main()
