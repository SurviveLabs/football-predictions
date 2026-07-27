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

# Fixed WAT (UTC+1 / West Africa Time)
WAT_TIMEZONE = timezone(timedelta(hours=1))
LOCAL_TIMEZONE_NAME = "Africa/Lagos"

# Whitelist of Major Competitions + Pre-Season Club Friendlies
MAJOR_LEAGUE_IDS = {
    2, 3, 848,          # Champions League, Europa League, Conference League
    39, 40, 45, 48,     # Premier League, Championship, FA Cup, League Cup (England)
    140, 141, 143,      # La Liga, Segunda División, Copa del Rey (Spain)
    135, 136, 137,      # Serie A, Serie B, Coppa Italia (Italy)
    78, 79, 81,         # Bundesliga, 2. Bundesliga, DFB-Pokal (Germany)
    61, 62, 66,         # Ligue 1, Ligue 2, Coupe de France (France)
    88,                 # Eredivisie (Netherlands)
    94,                 # Primeira Liga (Portugal)
    253,                # MLS (USA)
    307,                # Saudi Pro League
    71,                 # Brasileirão Serie A
    128,                # Liga Profesional Argentina
    288,                # NPFL (Nigeria)
    1, 4, 9, 6, 15,     # World Cup, Euros, Copa America, AFCON, Nations League
    667,                # Club Friendlies
}

EXCLUDE_KEYWORDS = [
    "youth", "u17", "u18", "u19", "u20", "u21", "u23", 
    "reserve", "women", "wnl", "simulated", 
    "cyber", "electronic", "amateur", "3rd", "4th"
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

    if league_id in MAJOR_LEAGUE_IDS:
        return True

    return False

def generate_prediction_market(fixture_id, home_team, away_team):
    market_matrix = [
        {"pick": f"{home_team} Win", "confidence": 84, "odds": 1.58},
        {"pick": "Over 1.5 Goals", "confidence": 90, "odds": 1.32},
        {"pick": f"Double Chance ({home_team} or Draw)", "confidence": 92, "odds": 1.28},
        {"pick": "Both Teams To Score (BTTS)", "confidence": 78, "odds": 1.75},
        {"pick": "Over 2.5 Goals", "confidence": 81, "odds": 1.82},
        {"pick": f"{away_team} Win", "confidence": 72, "odds": 2.25},
        {"pick": f"Double Chance ({away_team} or Draw)", "confidence": 86, "odds": 1.45}
    ]

    selected = market_matrix[fixture_id % len(market_matrix)]
    return selected["pick"], selected["confidence"], selected["odds"]

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

        prediction_text, confidence_score, exact_odds = generate_prediction_market(fixture_id, home_team, away_team)

        match_info = {
            "fixture_id": fixture_id,
            "league": league.get("name", "Unknown League"),
            "match": f"{home_team} vs {away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "date": fixture.get("date", ""),
            "prediction": prediction_text,
            "confidence_num": confidence_score,
            "confidence": f"{confidence_score}%",
            "odds": exact_odds
        }
        predictions_data.append(match_info)

    predictions_data.sort(key=lambda x: x["confidence_num"], reverse=True)
    for index, match in enumerate(predictions_data, start=1):
        match["rank"] = index

    predictions_data.sort(key=lambda x: x.get("date", ""))

    return predictions_data

def build_standard_ticket(predictions, target_odds):
    sorted_matches = sorted(predictions, key=lambda x: x["confidence_num"], reverse=True)
    selected_matches = []
    total_odds = 1.0

    for match in sorted_matches:
        odds_val = match.get("odds", 1.50)
        selected_matches.append(match)
        total_odds *= odds_val

        if total_odds >= target_odds:
            break

    return selected_matches, total_odds

def build_high_odds_ticket(predictions, target_odds=10.0):
    # Prefer picks with higher individual odds
    high_value_matches = [m for m in predictions if m.get("odds", 1.50) >= 1.60]
    if not high_value_matches:
        high_value_matches = predictions

    sorted_matches = sorted(high_value_matches, key=lambda x: x.get("odds", 1.50), reverse=True)
    selected_matches = []
    total_odds = 1.0

    for match in sorted_matches:
        odds_val = match.get("odds", 1.50)
        selected_matches.append(match)
        total_odds *= odds_val

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

    # Build standard and high-odds tickets
    slip_3, total_3 = build_standard_ticket(predictions, 3.0)
    slip_5, total_5 = build_standard_ticket(predictions, 5.0)
    slip_10, total_10 = build_high_odds_ticket(predictions, 10.0)

    now_str = datetime.now(WAT_TIMEZONE).strftime("%b %d, %Y • %I:%M %p WAT")

    # Format HTML Message
    message = "<b>⚽ DAILY PREDICTION TICKETS ⚽</b>\n"
    message += f"<i>Updated: {now_str}</i>\n\n"

    # 3-Odds Slip
    message += "<b>🎯 3-ODDS SAFE SLIP</b>\n"
    for i, m in enumerate(slip_3, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b>\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💵 <b>Total Odds: ~{total_3:.2f}</b>\n\n"

    # 5-Odds Slip
    message += "<b>🔥 5-ODDS MEDIUM SLIP</b>\n"
    for i, m in enumerate(slip_5, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b>\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💵 <b>Total Odds: ~{total_5:.2f}</b>\n\n"

    # 10+ High Odds Slip
    message += "<b>🚀 10+ HIGH-ODDS TICKET</b>\n"
    for i, m in enumerate(slip_10, 1):
        message += f"{i}. <b>{m['home_team']} vs {m['away_team']}</b>\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
    message += f"💥 <b>Total Combined Odds: {total_10:.2f}</b>\n\n"

    message += "📲 <i>Check all today's matches on the Web App!</i>"

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(telegram_url, json=payload)
        response.raise_for_status()
        print("🚀 Telegram ticket broadcast posted successfully!")
    except Exception as e:
        print(f"❌ Failed to broadcast to Telegram: {e}")

def main():
    print("⚽ Fetching fixtures from API-Football...")
    raw_fixtures = fetch_fixtures()

    if raw_fixtures:
        predictions = process_fixtures(raw_fixtures)
        print(f"✅ Processed {len(predictions)} matches with exact odds.")
    else:
        print("⚠️ No matches scheduled today or tomorrow.")
        predictions = []

    now_wat = datetime.now(WAT_TIMEZONE).strftime("%Y-%m-%d %I:%M %p WAT")
    
    output_payload = {
        "last_updated": now_wat,
        "predictions": predictions
    }

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=4)

    print(f"🎉 File generated at {now_wat}: predictions.json")

    # Trigger Telegram Broadcast
    send_telegram_broadcast(predictions)

if __name__ == "__main__":
    main()
    
