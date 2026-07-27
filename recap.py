import os
import json
import requests
from datetime import datetime, timezone, timedelta

# API Configuration
API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"

# Telegram Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "x-apisports-key": API_KEY
}

WAT_TIMEZONE = timezone(timedelta(hours=1))

def fetch_finished_fixtures(target_date_str):
    """Fetches finished fixtures for a specific date from API-Football."""
    if not API_KEY:
        print("❌ Error: FOOTBALL_API_KEY environment variable is missing.")
        return {}

    print(f"🔍 Fetching finished results for date: {target_date_str}")

    try:
        params = {
            "date": target_date_str,
            "status": "FT"  # FT = Finished
        }
        response = requests.get(API_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        fixtures = response.json().get("response", [])

        results_map = {}
        for item in fixtures:
            fix_id = item.get("fixture", {}).get("id")
            goals = item.get("goals", {})
            results_map[fix_id] = {
                "home_goals": goals.get("home", 0),
                "away_goals": goals.get("away", 0),
                "status": item.get("fixture", {}).get("status", {}).get("short")
            }
        return results_map
    except Exception as e:
        print(f"❌ Failed to fetch fixture results: {e}")
        return {}

def evaluate_pick(prediction_text, home_goals, away_goals, home_team, away_team):
    """Evaluates whether a match prediction won or lost based on actual goals."""
    total_goals = home_goals + away_goals
    pick_lower = prediction_text.lower()

    if "over 1.5 goals" in pick_lower:
        return total_goals > 1.5
    elif "over 2.5 goals" in pick_lower:
        return total_goals > 2.5
    elif "both teams to score" in pick_lower or "btts" in pick_lower:
        return home_goals > 0 and away_goals > 0
    elif f"{home_team.lower()} win" in pick_lower:
        return home_goals > away_goals
    elif f"{away_team.lower()} win" in pick_lower:
        return away_goals > home_goals
    elif f"double chance ({home_team.lower()} or draw)" in pick_lower:
        return home_goals >= away_goals
    elif f"double chance ({away_team.lower()} or draw)" in pick_lower:
        return away_goals >= home_goals
    elif f"{away_team.lower()} draw no bet" in pick_lower:
        return away_goals > home_goals
    elif f"{home_team.lower()} draw no bet" in pick_lower:
        return home_goals > away_goals

    return home_goals > away_goals if "win" in pick_lower else True

def evaluate_ticket(ticket_matches, results_map):
    """Evaluates all matches inside a ticket slip."""
    total_matches = len(ticket_matches)
    won_matches = 0
    pending_or_missing = 0

    for match in ticket_matches:
        fix_id = match.get("fixture_id")
        if fix_id in results_map:
            res = results_map[fix_id]
            is_win = evaluate_pick(
                match["prediction"],
                res["home_goals"],
                res["away_goals"],
                match["home_team"],
                match["away_team"]
            )
            if is_win:
                won_matches += 1
        else:
            pending_or_missing += 1

    slip_won = (won_matches == (total_matches - pending_or_missing)) and total_matches > 0
    return slip_won, won_matches, total_matches - pending_or_missing

def send_recap_broadcast():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram credentials missing. Skipping recap.")
        return

    if not os.path.exists("predictions.json"):
        print("⚠️ No predictions.json file found to evaluate.")
        return

    with open("predictions.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    predictions = data.get("predictions", [])
    if not predictions:
        print("⚠️ No predictions in predictions.json.")
        return

    # Check both today and yesterday to cover late-night/overnight games
    now_dt = datetime.now(WAT_TIMEZONE)
    today_str = now_dt.strftime("%Y-%m-%d")
    yesterday_str = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    results_map = fetch_finished_fixtures(yesterday_str)
    results_map.update(fetch_finished_fixtures(today_str))

    if not results_map:
        print("ℹ️ No finished matches recorded yet.")
        return

    from main import build_diverse_ticket
    slip_3, total_3 = build_diverse_ticket(predictions, 3.0, sort_by="confidence")
    slip_5, total_5 = build_diverse_ticket(predictions, 5.0, sort_by="confidence")
    slip_10, total_10 = build_diverse_ticket(predictions, 10.0, sort_by="odds")

    won_3, pass_3, count_3 = evaluate_ticket(slip_3, results_map)
    won_5, pass_5, count_5 = evaluate_ticket(slip_5, results_map)
    won_10, pass_10, count_10 = evaluate_ticket(slip_10, results_map)

    recap_date = (now_dt - timedelta(days=1)).strftime("%b %d, %Y")

    # Construct Recap Message
    message = "<b>🏆 YESTERDAY'S TICKET RESULTS RECAP 🏆</b>\n"
    message += f"<i>Date: {recap_date}</i>\n\n"

    status_icon = lambda won: "✅ <b>WON</b>" if won else "❌ <b>LOST</b>"

    message += f"🎯 <b>3-Odds Safe Slip:</b> {status_icon(won_3)} ({pass_3}/{count_3} Passed)\n"
    message += f"🔥 <b>5-Odds Medium Slip:</b> {status_icon(won_5)} ({pass_5}/{count_5} Passed)\n"
    message += f"🚀 <b>10+ High-Odds Ticket:</b> {status_icon(won_10)} ({pass_10}/{count_10} Passed)\n\n"

    message += "💬 <i>Today's fresh tickets are dropping in a few minutes! Stay tuned.</i> 🚀"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(telegram_url, json=payload)
        response.raise_for_status()
        print("🎉 Morning ticket recap posted successfully to Telegram!")
    except Exception as e:
        print(f"❌ Failed to send ticket recap: {e}")

if __name__ == "__main__":
    send_recap_broadcast()
    
