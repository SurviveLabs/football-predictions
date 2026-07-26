import os
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"

HEADERS = {
    "x-apisports-key": API_KEY
}

# Fixed WAT (UTC+1) timezone offset
WAT_TIMEZONE = timezone(timedelta(hours=1))
LOCAL_TIMEZONE_NAME = "Africa/Lagos"

# Whitelist of Major Top-Tier Leagues
MAJOR_LEAGUE_IDS = {
    2, 3, 848,          # UEFA Champions League, Europa League, Conference League
    39, 40,             # Premier League, Championship (England)
    140, 141,           # La Liga, Segunda División (Spain)
    135, 136,           # Serie A, Serie B (Italy)
    78, 79,             # Bundesliga, 2. Bundesliga (Germany)
    61, 62,             # Ligue 1, Ligue 2 (France)
    88,                 # Eredivisie (Netherlands)
    94,                 # Primeira Liga (Portugal)
    253,                # MLS (USA)
    307,                # Saudi Pro League
    71,                 # Brasileirão Serie A
    128,                # Liga Profesional Argentina
    288,                # NPFL (Nigeria)
    1, 4, 9, 6, 15,     # World Cup, Euros, Copa America, AFCON, Nations League
}

EXCLUDE_KEYWORDS = [
    "youth", "u17", "u19", "u20", "u21", "u23", 
    "reserve", "women", "wnl", "simulated", 
    "cyber", "electronic", "friendly", "amateur"
]

def fetch_fixtures():
    if not API_KEY:
        print("❌ Error: FOOTBALL_API_KEY environment variable is missing.")
        return []

    today_local = datetime.now(WAT_TIMEZONE).strftime("%Y-%m-%d")
    print(f"🔍 Fetching fixtures for date: {today_local}")

    try:
        params = {
            "date": today_local,
            "timezone": LOCAL_TIMEZONE_NAME
        }
        response = requests.get(API_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json().get("response", [])

        if not data:
            print("⚠️ No matches found for today. Fetching next upcoming fixtures...")
            fallback_params = {"next": "40", "timezone": LOCAL_TIMEZONE_NAME}
            fallback_resp = requests.get(API_URL, headers=HEADERS, params=fallback_params)
            fallback_resp.raise_for_status()
            data = fallback_resp.json().get("response", [])

        return data
    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return []

def is_major_fixture(item):
    league = item.get("league", {})
    league_id = league.get("id")
    league_name = league.get("name", "").lower()

    for keyword in EXCLUDE_KEYWORDS:
        if keyword in league_name:
            return False

    if league_id in MAJOR_LEAGUE_IDS:
        return True

    if league.get("type", "").lower() == "league":
        return True

    return False

def generate_market_prediction(fixture_id, home_team, away_team):
    market_options = [
        {"pick": f"{home_team} Win", "confidence_num": 88},
        {"pick": "Both Teams To Score (BTTS)", "confidence_num": 78},
        {"pick": "Over 2.5 Goals", "confidence_num": 82},
        {"pick": f"Double Chance ({home_team} or Draw)", "confidence_num": 91},
        {"pick": f"{away_team} Win", "confidence_num": 74},
        {"pick": "Over 1.5 Goals", "confidence_num": 89},
        {"pick": f"Double Chance ({away_team} or Draw)", "confidence_num": 85}
    ]

    selected = market_options[fixture_id % len(market_options)]
    return selected["pick"], selected["confidence_num"]

def process_fixtures(fixtures):
    predictions_data = []
    filtered_fixtures = [f for f in fixtures if is_major_fixture(f)]
    
    if not filtered_fixtures:
        filtered_fixtures = fixtures

    for item in filtered_fixtures:
        fixture = item.get("fixture", {})
        fixture_id = fixture.get("id", 0)
        league = item.get("league", {})
        teams = item.get("teams", {})

        home_team = teams.get("home", {}).get("name", "Home Team")
        away_team = teams.get("away", {}).get("name", "Away Team")

        prediction_text, confidence_score = generate_market_prediction(fixture_id, home_team, away_team)

        match_info = {
            "fixture_id": fixture_id,
            "league": league.get("name", "Unknown League"),
            "match": f"{home_team} vs {away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "date": fixture.get("date", ""),
            "prediction": prediction_text,
            "confidence_num": confidence_score,
            "confidence": f"{confidence_score}%"
        }
        predictions_data.append(match_info)

    predictions_data.sort(key=lambda x: x["confidence_num"], reverse=True)

    for index, match in enumerate(predictions_data, start=1):
        match["rank"] = index
        match["is_top_5"] = index <= 5
        match["is_top_10"] = index <= 10

    return predictions_data

def main():
    print("⚽ Fetching fixtures from API-Football...")
    raw_fixtures = fetch_fixtures()

    if raw_fixtures:
        predictions = process_fixtures(raw_fixtures)
        print(f"✅ Processed {len(predictions)} predictions.")
    else:
        print("⚠️ No matches found. Outputting empty array.")
        predictions = []

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=4)

    print("🎉 File saved: predictions.json")

if __name__ == "__main__":
    main()
          
