import os
import json
import logging
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Токен будет подставлен из настроек Render
FOXY_SERVICE_ID = "0bb2356a781f"
FOXY_BOT_LINK = "https://t.me/foxcoingame_bot/app"

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === ПРОСТАЯ БАЗА ДАННЫХ (JSON-файл) ===
DB_FILE = "users.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f)

# === КОМАНДЫ ТЕЛЕГРАМ БОТА ===
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.chat.id)
    users = load_users()
    if user_id not in users:
        users[user_id] = {"balance": 0}
        save_users(users)
    bot.reply_to(message, f"Привет! Твой баланс: {users[user_id]['balance']} FC\nИспользуй /shop для покупок.")

@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = str(message.chat.id)
    users = load_users()
    balance = users.get(user_id, {}).get("balance", 0)
    bot.reply_to(message, f"💰 Твой баланс: {balance} FC")

@bot.message_handler(commands=['shop'])
def shop(message):
    user_id = message.chat.id
    # Генерируем ссылку на 100 FC с фиксированной суммой
    startapp = f"service_{FOXY_SERVICE_ID}__user_{user_id}__sum_100__lock_1"
    payment_url = f"{FOXY_BOT_LINK}?startapp={startapp}&topup_sum=100&topup_lock=1"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💎 Купить 100 FC", url=payment_url))
    bot.reply_to(message, "🛒 Магазин:\n100 FC = 100 единиц", reply_markup=keyboard)

# === ОБРАБОТЧИК CALLBACK ОТ FOXY COMPANY ===
@app.route('/callback', methods=['POST'])
def callback():
    data = request.get_json()
    logging.info(f"Получен callback: {data}")
    
    # Здесь Foxy Company присылает данные. Уточните названия полей в их документации
    user_id = str(data.get('user_id'))  # может быть 'user_id' или 'startapp' с параметром
    amount = int(data.get('amount', 0))
    
    if not user_id or not amount:
        return jsonify({'error': 'Invalid data'}), 400
    
    users = load_users()
    if user_id not in users:
        users[user_id] = {"balance": 0}
    users[user_id]['balance'] = users[user_id].get('balance', 0) + amount
    save_users(users)
    
    return jsonify({'status': 'ok'})

# === ЗДОРОВЬЕ ДЛЯ RENDER ===
@app.route('/')
def health():
    return "Bot is running", 200

# === ЗАПУСК ===
if __name__ == "__main__":
    # Flask запускается на порту, который даёт Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)