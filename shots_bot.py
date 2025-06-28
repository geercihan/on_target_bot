import os
import json
import requests
from datetime import datetime
import pytz

API_KEY = os.getenv("API_KEY", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
TIMEZONE = pytz.timezone("Africa/Tunis")
SENT_LOG_FILE = "sent_log.json"

# === Load sent alerts ===
def load_sent_alerts():
    if not os.path.exists(SENT_LOG_FILE):
        return {"case1": [], "case2": []}
    with open(SENT_LOG_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {"case1": [], "case2": []}

# === Save sent alerts ===
def save_sent_alerts(log):
    with open(SENT_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

# === Format time ===
def get_local_time():
    return datetime.now(TIMEZONE).strftime("%H:%M:%S")

# === Get live fixtures ===
def fetch_live_matches():
    url = "https://v3.football.api-sports.io/fixtures?live=all"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[ERROR] API response: {response.status_code}")
        return []
    return response.json().get("response", [])

# === Get statistics from correct endpoint ===
def fetch_statistics(fixture_id):
    url = f"https://v3.football.api-sports.io/fixtures/statistics?fixture={fixture_id}"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    return response.json().get("response", [])

# === Extract shots for both teams ===
def extract_shots(stat_list, home_id, away_id):
    on_home, off_home = 0, 0
    on_away, off_away = 0, 0
    for team_stats in stat_list:
        team_id = team_stats.get("team", {}).get("id")
        stats = team_stats.get("statistics", [])
        for s in stats:
            if s["type"] == "Shots on Goal":
                if team_id == home_id:
                    on_home = s["value"] or 0
                elif team_id == away_id:
                    on_away = s["value"] or 0
            elif s["type"] == "Shots off Goal":
                if team_id == home_id:
                    off_home = s["value"] or 0
                elif team_id == away_id:
                    off_away = s["value"] or 0
    return on_home, off_home, on_away, off_away

# === Send Telegram Alert ===
def send_alert(fixture, minute, on_total, off_total, on_home, on_away, case, home_rank, away_rank):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    league = fixture["league"]["name"]
    competition = fixture["league"].get("round", "N/A")
    time_str = get_local_time()

    msg = f"📊 <b>{home} vs {away}</b>\n🏆 <b>{league}</b> | {competition}\n"
    if home_rank: msg += f"📈 {home} Rank: <b>{home_rank}</b>\n"
    if away_rank: msg += f"📈 {away} Rank: <b>{away_rank}</b>\n"
    msg += f"\n⏱ Minute: <b>{minute}</b>\n"
    msg += f"🎯 On Target: <b>{on_total}</b>\n🚀 Off Target: <b>{off_total}</b>\n"
    msg += f"📍 Case Triggered: <b>{case}</b>\n🕒 <i>{time_str}</i>"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    r = requests.post(url, data=payload)
    print(f"[ALERT] Sent for {home} vs {away} | {case}")

# === Main Logic ===
def main():
    sent = load_sent_alerts()
    matches = fetch_live_matches()
    print(f"[INFO] Matches fetched: {len(matches)}")

    for match in matches:
        fixture_id = str(match["fixture"]["id"])
        minute = match["fixture"]["status"].get("elapsed", 0)
        score_home = match["goals"].get("home", 0)
        score_away = match["goals"].get("away", 0)
        home_team = match["teams"]["home"]["name"]
        away_team = match["teams"]["away"]["name"]
        home_id = match["teams"]["home"]["id"]
        away_id = match["teams"]["away"]["id"]
        league = match["league"]["name"]
        round_ = match["league"].get("round", "N/A")
        country = match["league"].get("country", "N/A")
        home_rank = match["teams"]["home"].get("league", {}).get("position")
        away_rank = match["teams"]["away"].get("league", {}).get("position")

        print(f"[CHECK] {home_team} vs {away_team} — ⏱ {minute}′")
        print(f"🏷️ Country: {country} | 🏆 League: {league} | 🪪 Round: {round_}")

        stats = fetch_statistics(fixture_id)
        if not stats or len(stats) < 2:
            print("[SKIP] ❌ No statistics available.")
            continue

        on_home, off_home, on_away, off_away = extract_shots(stats, home_id, away_id)
        on_total = on_home + on_away
        off_total = off_home + off_away

        print(f"[STATS] 🎯 On: {on_total} (Home: {on_home}, Away: {on_away}) | 🚀 Off: {off_total}")

        # === Case 1 ===
        if minute <= 16 and fixture_id not in sent["case1"]:
            if on_total >= 1 and (on_total + off_total) >= 3:
                send_alert(match, minute, on_total, off_total, on_home, on_away, "Case 1", home_rank, away_rank)
                sent["case1"].append(fixture_id)

        # === Case 2 ===
        if minute <= 25 and fixture_id not in sent["case2"]:
            if (score_home, score_away) in [(1, 0), (0, 1)] and on_home >= 2 and on_away >= 2:
                send_alert(match, minute, on_total, off_total, on_home, on_away, "Case 2", home_rank, away_rank)
                sent["case2"].append(fixture_id)

    save_sent_alerts(sent)

if __name__ == "__main__":
    main()
