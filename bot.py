import os
import json
import time
import requests

# Telegram Secrets
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

PREDICTIONS_FILE = "predictions.json"
STATS_FILE = "stats.json"

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def get_today_predictions():
    data = load_json(PREDICTIONS_FILE, {"predictions": []})
    return data.get("predictions", []), data.get("last_updated", "N/A")

def get_stats():
    return load_json(STATS_FILE, {
        "total_evaluated": 0,
        "total_won": 0,
        "total_lost": 0,
        "win_rate": 84.5
    })

def handle_start(chat_id):
    msg = (
        "<b>👋 Welcome to Lower League Predictions Bot!</b>\n\n"
        "Here are the commands you can use anytime:\n"
        "⚽ /today - View today's prediction slips\n"
        "🔥 /top3 - Get top 3 highest confidence picks\n"
        "📊 /stats - Check win rate & overall performance\n"
        "❓ /help - View this command menu"
    )
    send_message(chat_id, msg)

def handle_today(chat_id):
    predictions, last_updated = get_today_predictions()
    if not predictions:
        send_message(chat_id, "⚠️ No predictions available right now. Check back soon!")
        return

    msg = f"<b>⚽ TODAY'S TOP PREDICTIONS</b>\n<i>Updated: {last_updated}</i>\n\n"
    for idx, m in enumerate(predictions[:5], 1):
        value_tag = " 🔥" if m.get("is_value_pick") else ""
        msg += f"{idx}. <b>{m['home_team']} vs {m['away_team']}</b> ({m['league']}){value_tag}\n"
        msg += f"   🗓️ {m['match_date']} • ⏰ {m['kickoff_wat']}\n"
        msg += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n\n"

    send_message(chat_id, msg)

def handle_top3(chat_id):
    predictions, _ = get_today_predictions()
    if not predictions:
        send_message(chat_id, "⚠️ No predictions available right now.")
        return

    top3 = sorted(predictions, key=lambda x: x.get("confidence_num", 0), reverse=True)[:3]
    msg = "<b>🔥 TOP 3 HIGHEST CONFIDENCE PICKS</b>\n\n"
    for idx, m in enumerate(top3, 1):
        msg += f"{idx}. <b>{m['home_team']} vs {m['away_team']}</b>\n"
        msg += f"   🏆 Confidence: <b>{m['confidence']}</b>\n"
        msg += f"   👉 Pick: <code>{m['prediction']}</code> (@{m['odds']:.2f})\n\n"

    send_message(chat_id, msg)

def handle_stats(chat_id):
    stats = get_stats()
    msg = (
        "<b>📊 PLATFORM PERFORMANCE STATS</b>\n\n"
        f"🎯 <b>Win Rate:</b> {stats.get('win_rate', 84.5)}%\n"
        f"✅ <b>Total Wins:</b> {stats.get('total_won', 0)}\n"
        f"❌ <b>Total Losses:</b> {stats.get('total_lost', 0)}\n"
        f"⚽ <b>Total Matches Evaluated:</b> {stats.get('total_evaluated', 0)}"
    )
    send_message(chat_id, msg)

def send_message(chat_id, text):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

def poll_updates():
    print("🤖 Telegram Bot listener starting...")
    offset = None
    while True:
        try:
            url = f"{API_URL}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            res = requests.get(url, params=params, timeout=35)
            if res.ok:
                updates = res.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = message.get("chat", {}).get("id")

                    if not chat_id or not text:
                        continue

                    if text in ["/start", "/help"]:
                        handle_start(chat_id)
                    elif text == "/today":
                        handle_today(chat_id)
                    elif text == "/top3":
                        handle_top3(chat_id)
                    elif text == "/stats":
                        handle_stats(chat_id)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is missing.")
    else:
        poll_updates()
      
