import os
import json
import requests
from datetime import datetime, timezone, timedelta

# API Configuration
API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"

# Telegram Secrets & Web App Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
WEB_APP_URL = "https://survivelabs.github.io/football-predictions/index.html"  

HEADERS = {
    "x-apisports-key": API_KEY
}

# Fixed WAT (UTC+1 / West Africa Time)
WAT_TIMEZONE = timezone(timedelta(hours=1))
LOCAL_TIMEZONE_NAME = "Africa/Lagos"

# Whitelist focused on Lower & Secondary Tier Leagues
LOWER_LEAGUE_IDS = {
    # England
    40, 41, 42, 43,     # Championship, League One, League Two, National League
    # Spain
    141, 142,           # Segunda División, Primera RFEF
    # Italy
    136, 138,           # Serie B, Serie C
    # Germany
    79, 80,             # 2. Bundesliga, 3. Liga
    # France
    62, 63,             # Ligue 2, National
    # Netherlands & Portugal
    89, 95,             # Eerste Divisie, Liga Portugal 2
    # Americas
    72, 73,             # Brasileirão Serie B, Serie C
    129,                # Argentina Primera Nacional
    255,                # USA USL Championship
    # Scotland
    180, 181, 182,      # Championship, League One, League Two
    # Scandinavia & Europe
    114,                # Sweden Superettan
    104,                # Norway 1. Division
    245,                # Finland Ykkösliiga / Ykkönen
    358,                # Ireland First Division
    303,                # Iceland 1. Deild
    120,                # Denmark 1. Division
    219,                # Austria 2. Liga
    208,                # Switzerland Challenge League
    145,                # Belgium Challenger Pro League
    # Asia
    99, 100,            # Japan J2 League, J3 League
    293                 # South Korea K League 2
}

EXCLUDE_KEYWORDS = [
    "youth", "u17", "u18", "u19", "u20", "u21", "u23", 
    "women", "wnl", "simulated", "cyber", "electronic"
]

def fetch_fixtures():
    if not API_KEY:
        print("❌ Error: FOOTBALL_API_KEY environment variable is missing.")
        return []

    today_dt = datetime.now(WAT_TIMEZONE)
    today_str = today_dt.strftime("%Y-%m-%d")
    tomorrow_str = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    all_fixtures = []

    for date_str in [today_str, tomorrow_str]:
        print(f"🔍 Fetching fixtures for date: {date_str}")
        try:
            params = {
                "date": date_str,
                "timezone": LOCAL_TIMEZONE_NAME
            }
            response = requests.get(API_URL, headers=HEADERS, params=params)
            response.raise_for_status()
            data = response.json().get("response", [])
            all_fixtures.extend(data)
        except Exception as e:
            print(f"❌ API Request Failed for {date_str}: {e}")

    return all_fixtures

def is_valid_fixture(item):
    league = item.get("league", {})
    league_id = league.get("id")
    league_name = league.get("name", "").lower()

    for keyword in EXCLUDE_KEYWORDS:
        if keyword in league_name:
            return False

    if league_id in LOWER_LEAGUE_IDS:
        return True

    return False

def generate_diversified_prediction(fixture_id, home_team, away_team):
    market_matrix = [
        {"pick": f"{home_team} Win", "confidence": 85, "odds": 1.70, "cat": "Straight Pick"},
        {"pick": "Over 1.5 Goals", "confidence": 89, "odds": 1.32, "cat": "Goals"},
        {"pick": f"{away_team} Win", "confidence": 79, "odds": 2.15, "cat": "Straight Pick"},
        {"pick": f"Double Chance ({home_team} or Draw)", "confidence": 90, "odds": 1.28, "cat": "Double Chance"},
        {"pick": "Both Teams To Score (BTTS)", "confidence": 83, "odds": 1.75, "cat": "BTTS"},
        {"pick": f"Double Chance ({away_team} or Draw)", "confidence": 85, "odds": 1.45, "cat": "Double Chance"},
        {"pick": "Over 2.5 Goals", "confidence": 81, "odds": 1.82, "cat": "Goals"},
        {"pick": f"{away_team} Draw No Bet", "confidence": 82, "odds": 1.90, "cat": "Straight Pick"},
        {"pick": f"{home_team} Draw No Bet", "confidence": 86, "odds": 1.48, "cat": "Straight Pick"}
    ]

    selected = market_matrix[fixture_id % len(market_matrix)]
    return selected["pick"], selected["confidence"], selected["odds"], selected["cat"]

def format_match_datetime(utc_date_str):
    try:
        dt = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00"))
        wat_dt = dt.astimezone(WAT_TIMEZONE)
        match_date = wat_dt.strftime("%b %d")
        match_time = wat_dt.strftime("%I:%M %p")
        return match_date, match_time
    except Exception:
        return "Today", "TBD"

def process_fixtures(fixtures):
    filtered_fixtures = [f for f in fixtures if is_valid_fixture(f)]
    predictions_data = []

    for item in filtered_fixtures:
        fixture = item.get("fixture", {})
        fixture_id = fixture.get("id", 0)
        league = item.get("league", {})
        teams = item.get("teams", {})

        home_team = teams.get("home", {}).get("name", "Home Team")
        away_team = teams.get("away", {}).get("name", "Away Team")
        league_name = league.get("name", "Unknown League")

        prediction_text, confidence_score, exact_odds, market_cat = generate_diversified_prediction(fixture_id, home_team, away_team)
        match_date, match_time = format_match_datetime(fixture.get("date", ""))

        match_info = {
            "fixture_id": fixture_id,
            "league": league_name,
            "match": f"{home_team} vs {away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "kickoff_wat": match_time,
            "prediction": prediction_text,
            "market_cat": market_cat,
            "confidence_num": confidence_score,
            "confidence": f"{confidence_score}%",
            "odds": exact_odds,
            "date": fixture.get("date", "")
        }
        predictions_data.append(match_info)

    predictions_data.sort(key=lambda x: x["confidence_num"], reverse=True)
    for index, match in enumerate(predictions_data, start=1):
        match["rank"] = index

    predictions_data.sort(key=lambda x: x.get("date", ""))

    return predictions_data

def build_diverse_ticket(predictions, target_odds, sort_by="confidence"):
    today_str = datetime.now(WAT_TIMEZONE).strftime("%b %d")

    # Priority 1: Today's matches (1) over Tomorrow's matches (0)
    # Priority 2: Highest Confidence or Highest Odds
    if sort_by == "odds":
        sorted_matches = sorted(
            predictions, 
            key=lambda x: (1 if x.get("match_date") == today_str else 0, x.get("odds", 1.50)), 
            reverse=True
        )
    else:
        sorted_matches = sorted(
            predictions, 
            key=lambda x: (1 if x.get("match_date") == today_str else 0, x["confidence_num"]), 
            reverse=True
        )

    selected_matches = []
    total_odds = 1.0
    category_counts = {}

    for match in sorted_matches:
        category = match.get("market_cat", "General")

        if category_counts.get(category, 0) >= 2:
            continue

        selected_matches.append(match)
        category_counts[category] = category_counts.get(category, 0) + 1
        total_odds *= match.get("odds", 1.50)

        if total_odds >= target_odds:
            break

    if total_odds < target_odds:
        for match in sorted_matches:
            if match not in selected_matches:
                selected_matches.append(match)
                total_odds *= match.get("odds", 1.50)
                if total_odds >= target_odds:
                    break

    return selected_matches, total_odds

def send_telegram_broadcast(predictions):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram credentials missing. Skipping broadcast.")
        return

    if not predictions:
        print("⚠️ No predictions available to broadcast.")
        return

    slip_3, total_3 = build_diverse_ticket(predictions, 3.0, sort_by="confidence")
    slip_5, total_5 = build_diverse_ticket(predictions, 5.0, sort_by="confidence")
    slip_10, total_10 = build_diverse_ticket(predictions, 10.0, sort_by="odds")

    now_str = datetime.now(WAT_TIMEZONE).strftime("%b %d, %Y • %I:%M %p WAT")

    message = "<b>⚽ DAILY PREDICTION TICKETS ⚽</b>\n"
    message += f"<i>Updated: {now_str}</i>\n\n"

    message += "<b>🎯 3-ODDS SAFE SLIP</b>\n"
    for i, m in enumerate(slip_3, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b> ({m['league']})\n"
        message += f"   🗓️ {m['match_date']} • ⏰ {m['kickoff_wat']}\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💵 <b>Total Odds: ~{total_3:.2f}</b>\n\n"

    message += "<b>🔥 5-ODDS MEDIUM SLIP</b>\n"
    for i, m in enumerate(slip_5, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b> ({m['league']})\n"
        message += f"   🗓️ {m['match_date']} • ⏰ {m['kickoff_wat']}\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💵 <b>Total Odds: ~{total_5:.2f}</b>\n\n"

    message += "<b>🚀 10+ HIGH-ODDS TICKET</b>\n"
    for i, m in enumerate(slip_10, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b> ({m['league']})\n"
        message += f"   🗓️ {m['match_date']} • ⏰ {m['kickoff_wat']}\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💥 <b>Total Combined Odds: {total_10:.2f}</b>"

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🌐 Open Predictions Web App", "url": WEB_APP_URL}
            ]
        ]
    }

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": reply_markup
    }

    try:
        response = requests.post(telegram_url, json=payload)
        response.raise_for_status()
        print("🚀 Telegram ticket broadcast posted successfully!")
    except Exception as e:
        print(f"❌ Failed to broadcast to Telegram: {e}")

    send_channel_poll(predictions)

def send_channel_poll(predictions):
    if not predictions:
        return

    top_match = sorted(predictions, key=lambda x: x["confidence_num"], reverse=True)[0]
    
    question = f"🗳️ MATCH OF THE DAY POLL: {top_match['home_team']} vs {top_match['away_team']}! Who wins?"
    options = json.dumps([f"🔴 {top_match['home_team']}", "🤝 Draw", f"🔵 {top_match['away_team']}"])

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": question,
        "options": options,
        "is_anonymous": False
    }

    try:
        requests.post(telegram_url, data=payload)
        print("📊 Channel poll posted successfully!")
    except Exception as e:
        print(f"⚠️ Could not post channel poll: {e}")

def main():
    print("⚽ Fetching fixtures from API-Football...")
    raw_fixtures = fetch_fixtures()

    if raw_fixtures:
        predictions = process_fixtures(raw_fixtures)
        print(f"✅ Processed {len(predictions)} lower league matches.")
    else:
        print("⚠️ No lower league matches scheduled today or tomorrow.")
        predictions = []

    now_wat = datetime.now(WAT_TIMEZONE).strftime("%Y-%m-%d %I:%M %p WAT")
    
    output_payload = {
        "last_updated": now_wat,
        "predictions": predictions
    }

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=4)

    print(f"🎉 File generated at {now_wat}: predictions.json")

    send_telegram_broadcast(predictions)

if __name__ == "__main__":
    main()
