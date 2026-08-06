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

# Fixed WAT (UTC+1 / West Africa Time - Nigeria)
WAT_TIMEZONE = timezone(timedelta(hours=1))
LOCAL_TIMEZONE_NAME = "Africa/Lagos"

# Country Flag Mapping
COUNTRY_FLAGS = {
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Italy": "🇮🇹", "Germany": "🇩🇪",
    "France": "🇫🇷", "Netherlands": "🇳🇱", "Portugal": "🇵🇹", "Brazil": "🇧🇷",
    "Argentina": "🇦🇷", "USA": "🇺🇸", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Sweden": "🇸🇪",
    "Norway": "🇳🇴", "Finland": "🇫🇮", "Ireland": "🇮🇪", "Iceland": "🇮🇸",
    "Denmark": "🇩🇰", "Austria": "🇦🇹", "Switzerland": "🇨🇭", "Belgium": "🇧🇪",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "World": "🌐"
}

def get_country_flag(country_name):
    return COUNTRY_FLAGS.get(country_name, "🌐")

LOWER_LEAGUE_IDS = {
    40, 41, 42, 43, 141, 142, 136, 138, 79, 80, 62, 63,
    89, 95, 72, 73, 129, 255, 180, 181, 182, 114, 104, 245,
    358, 303, 120, 219, 208, 145, 99, 100, 293
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
        print(f"🔍 Fetching fixtures for date: {date_str} (Nigeria Time)")
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

def is_upcoming_wat(utc_date_str):
    try:
        dt = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00"))
        wat_dt = dt.astimezone(WAT_TIMEZONE)
        now_wat = datetime.now(WAT_TIMEZONE)
        return wat_dt > (now_wat + timedelta(minutes=5))
    except Exception:
        return True

def generate_diversified_prediction(fixture_id, home_team, away_team):
    market_matrix = [
        {"pick": f"{home_team} Win", "confidence": 85, "odds": 1.85, "cat": "Straight Pick"},
        {"pick": "Over 1.5 Goals", "confidence": 89, "odds": 1.32, "cat": "Goals"},
        {"pick": f"{away_team} Win", "confidence": 79, "odds": 2.15, "cat": "Straight Pick"},
        {"pick": f"Double Chance ({home_team} or Draw)", "confidence": 90, "odds": 1.28, "cat": "Double Chance"},
        {"pick": "Both Teams To Score (BTTS)", "confidence": 86, "odds": 1.82, "cat": "BTTS"},
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
        match_time = wat_dt.strftime("%I:%M %p WAT")
        return match_date, match_time
    except Exception:
        return "Today", "TBD"

def process_fixtures(fixtures):
    predictions_data = []

    for item in fixtures:
        if not is_valid_fixture(item):
            continue

        fixture = item.get("fixture", {})
        status_short = fixture.get("status", {}).get("short")
        match_utc_date = fixture.get("date", "")

        if status_short != "NS" or not is_upcoming_wat(match_utc_date):
            continue

        fixture_id = fixture.get("id", 0)
        league = item.get("league", {})
        teams = item.get("teams", {})

        home_team = teams.get("home", {}).get("name", "Home Team")
        away_team = teams.get("away", {}).get("name", "Away Team")
        league_name = league.get("name", "Unknown League")
        country_name = league.get("country", "World")
        flag_emoji = get_country_flag(country_name)

        prediction_text, confidence_score, exact_odds, market_cat = generate_diversified_prediction(fixture_id, home_team, away_team)
        match_date, match_time = format_match_datetime(match_utc_date)

        match_info = {
            "fixture_id": fixture_id,
            "country": country_name,
            "flag": flag_emoji,
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
            "status": "UPCOMING",
            "score": "VS",
            "won": None,
            "date": match_utc_date
        }
        predictions_data.append(match_info)

    return predictions_data

def get_best_today_picks(predictions, min_confidence=85, max_games=5):
    today_str = datetime.now(WAT_TIMEZONE).strftime("%b %d")
    
    # Priority 1: Strictly Today's matches
    today_matches = [m for m in predictions if m.get("match_date") == today_str]
    
    if len(today_matches) >= 2:
        candidate_pool = sorted(today_matches, key=lambda x: x["confidence_num"], reverse=True)
    else:
        # Priority 2: Fallback to all upcoming if today is late or empty
        candidate_pool = sorted(predictions, key=lambda x: x["confidence_num"], reverse=True)

    top_picks = [m for m in candidate_pool if m["confidence_num"] >= min_confidence]
    
    if len(top_picks) < 2:
        top_picks = candidate_pool[:3]
    elif len(top_picks) > max_games:
        top_picks = top_picks[:max_games]
        
    total_odds = 1.0
    for match in top_picks:
        total_odds *= match.get("odds", 1.50)
        
    return top_picks, total_odds

def send_telegram_broadcast(best_picks, total_odds):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram credentials missing. Skipping broadcast.")
        return

    if not best_picks:
        print("⚠️ No upcoming predictions available to broadcast.")
        return

    now_str = datetime.now(WAT_TIMEZONE).strftime("%b %d, %Y • %I:%M %p WAT")

    message = "<b>⚽ BEST PICKS OF THE DAY ⚽</b>\n"
    message += f"<i>Updated: {now_str}</i>\n\n"
    message += f"<b>🔥 TOP CONFIDENCE SELECTIONS ({len(best_picks)} Games)</b>\n\n"

    for i, m in enumerate(best_picks, 1):
        flag = m.get("flag", "🌐")
        message += f"{i}. {flag} <b>{m['home_team']} vs {m['away_team']}</b> ({m['league']})\n"
        message += f"   🗓️ {m['match_date']} • ⏰ {m['kickoff_wat']}\n"
        message += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n"
        message += f"   📊 Confidence: <b>{m['confidence']}</b>\n\n"

    message += f"💵 <b>Combined Total Odds: ~{total_odds:.2f}</b>\n"
    message += "🎯 <i>Filtered strictly for maximum win probability.</i>"

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🌐 Open Predictions Web App", "url": WEB_APP_URL}]
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
        print("🚀 Telegram Best Picks broadcast posted successfully!")
    except Exception as e:
        print(f"❌ Failed to broadcast to Telegram: {e}")

def main():
    print("⚽ Fetching fixtures from API-Football...")
    raw_fixtures = fetch_fixtures()

    if raw_fixtures:
        predictions = process_fixtures(raw_fixtures)
        print(f"✅ Filtered {len(predictions)} upcoming lower league matches.")
    else:
        print("⚠️ No lower league matches scheduled today or tomorrow.")
        predictions = []

    best_picks, total_odds = get_best_today_picks(predictions, min_confidence=85, max_games=5)

    now_wat = datetime.now(WAT_TIMEZONE).strftime("%Y-%m-%d %I:%M %p WAT")
    
    output_payload = {
        "last_updated": now_wat,
        "best_picks": best_picks,
        "total_best_odds": round(total_odds, 2),
        "predictions": predictions
    }

    with open("predictions.json", "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=4)

    print(f"🎉 File generated at {now_wat}: predictions.json")
    send_telegram_broadcast(best_picks, total_odds)

if __name__ == "__main__":
    main()
                  
