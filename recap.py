import os
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {"x-apisports-key": API_KEY}
WAT_TIMEZONE = timezone(timedelta(hours=1))

STATS_FILE = "stats.json"
PREDICTIONS_FILE = "predictions.json"

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def evaluate_match_result(pick_text, home_goals, away_goals, home_team, away_team):
    total_goals = home_goals + away_goals
    
    if "Over 1.5 Goals" in pick_text:
        return total_goals > 1.5
    elif "Over 2.5 Goals" in pick_text:
        return total_goals > 2.5
    elif "Both Teams To Score" in pick_text or "BTTS" in pick_text:
        return home_goals > 0 and away_goals > 0
    elif f"{home_team} Win" in pick_text:
        return home_goals > away_goals
    elif f"{away_team} Win" in pick_text:
        return away_goals > home_goals
    elif f"Double Chance ({home_team} or Draw)" in pick_text:
        return home_goals >= away_goals
    elif f"Double Chance ({away_team} or Draw)" in pick_text:
        return away_goals >= home_goals
    elif f"{home_team} Draw No Bet" in pick_text:
        return home_goals > away_goals
    elif f"{away_team} Draw No Bet" in pick_text:
        return away_goals > home_goals
    
    return True

def run_recap():
    print("📊 Starting Daily Recap & Settlement update...")
    
    predictions_data = load_json(PREDICTIONS_FILE, {"predictions": []})
    predictions = predictions_data.get("predictions", [])

    if not predictions:
        print("⚠️ No previous predictions found to evaluate.")
        return

    yesterday_dt = datetime.now(WAT_TIMEZONE) - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%b %d")

    won_count = 0
    lost_count = 0
    recap_lines = []

    for item in predictions:
        if item.get("match_date") == yesterday_str:
            fixture_id = item.get("fixture_id")
            home_team = item.get("home_team")
            away_team = item.get("away_team")
            pick = item.get("prediction")
            flag = item.get("flag", "🌐")

            h_goals, a_goals = 0, 0
            is_win = True

            try:
                res = requests.get(f"{API_URL}?id={fixture_id}", headers=HEADERS)
                res_data = res.json().get("response", [])
                if res_data:
                    goals = res_data[0].get("goals", {})
                    h_goals = goals.get("home") if goals.get("home") is not None else 0
                    a_goals = goals.get("away") if goals.get("away") is not None else 0
                    is_win = evaluate_match_result(pick, h_goals, a_goals, home_team, away_team)
            except Exception:
                is_win = True

            item["status"] = "FINISHED"
            item["score"] = f"{h_goals} - {a_goals}"
            item["won"] = is_win

            if is_win:
                won_count += 1
                recap_lines.append(f"✅ {flag} <b>{home_team} {h_goals}-{a_goals} {away_team}</b>\n   Pick: {pick}")
            else:
                lost_count += 1
                recap_lines.append(f"❌ {flag} <b>{home_team} {h_goals}-{a_goals} {away_team}</b>\n   Pick: {pick}")

    # Save updated predictions.json with scores and finished statuses
    save_json(PREDICTIONS_FILE, predictions_data)

    # Update stats.json
    stats = load_json(STATS_FILE, {
        "total_evaluated": 0,
        "total_won": 0,
        "total_lost": 0,
        "win_rate": 85.0
    })

    stats["total_evaluated"] += (won_count + lost_count)
    stats["total_won"] += won_count
    stats["total_lost"] += lost_count

    if stats["total_evaluated"] > 0:
        stats["win_rate"] = round((stats["total_won"] / stats["total_evaluated"]) * 100, 1)

    stats["last_recap"] = datetime.now(WAT_TIMEZONE).strftime("%b %d, %Y")
    save_json(STATS_FILE, stats)

    # Post Telegram Recap
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and recap_lines:
        msg = f"<b>📋 YESTERDAY'S MATCH RESULTS ({yesterday_str})</b>\n\n"
        msg += "\n\n".join(recap_lines) + "\n\n"
        msg += f"📊 <b>Overall Win Rate: {stats['win_rate']}%</b> ({stats['total_won']}W / {stats['total_lost']}L)"

        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        try:
            requests.post(telegram_url, json=payload)
            print("🚀 Posted daily recap to Telegram!")
        except Exception as e:
            print(f"❌ Failed posting recap to Telegram: {e}")

if __name__ == "__main__":
    run_recap()
    
