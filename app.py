import os
import json
import logging
import hmac
import hashlib
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === КОНФИГУРАЦИЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
FOXY_SERVICE_ID = os.environ.get("FOXY_SERVICE_ID")
FOXY_SECRET_KEY = os.environ.get("FOXY_SECRET_KEY")
FOXY_BOT_LINK = "https://t.me/foxcoingame_bot/app"

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === БАЗА ДАННЫХ (JSON) ===
DB_FILE = "users.json"

def load_users():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f)

def send_notification(chat_id, text):
    try:
        bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")

# === КОМАНДЫ БОТА ===
@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"/start от {message.chat.id}")
    user_id = str(message.chat.id)
    users = load_users()
    if user_id not in users:
        users[user_id] = {"balance": 0}
        save_users(users)
    bot.reply_to(message, f"Привет! Твой баланс: {users[user_id]['balance']} FC\nИспользуй /shop для покупок.")

@bot.message_handler(commands=['balance'])
def balance(message):
    logger.info(f"/balance от {message.chat.id}")
    user_id = str(message.chat.id)
    users = load_users()
    bal = users.get(user_id, {}).get("balance", 0)
    bot.reply_to(message, f"💰 Твой баланс: {bal} FC")

@bot.message_handler(commands=['shop'])
def shop(message):
    logger.info(f"/shop от {message.chat.id}")
    user_id = message.chat.id
    price = 100
    startapp = f"service_{FOXY_SERVICE_ID}__user_{user_id}__sum_{price}__lock_1"
    payment_url = f"{FOXY_BOT_LINK}?startapp={startapp}&topup_sum={price}&topup_lock=1"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💎 Купить 100 FC", url=payment_url))
    bot.reply_to(message, "🛒 Магазин:\n100 FC = 100 единиц", reply_markup=keyboard)

# === ОБРАБОТЧИК CALLBACK ОТ FOXY ===
@app.route('/callback', methods=['POST'])
def callback():
    data = request.get_json()
    if not data:
        logger.warning("Callback: нет JSON")
        return jsonify({'error': 'Invalid request'}), 400

    logger.info(f"Callback получен: {data}")

    tx_id = data.get('tx_id')
    user_id = data.get('user_id')
    amount = data.get('amount')
    sign = data.get('sign')

    if not all([tx_id, user_id, amount, sign]):
        logger.warning("Не хватает полей")
        return jsonify({'error': 'Missing fields'}), 400

    user_id = str(user_id)
    amount = int(amount)

    # Проверка подписи
    message = f"{tx_id}:{user_id}:{amount}"
    expected_sign = hmac.new(
        FOXY_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sign, sign):
        logger.error(f"Неверная подпись для tx {tx_id}")
        return jsonify({'error': 'Invalid signature'}), 403

    # Проверка дубликата транзакции
    processed_file = "processed_tx.json"
    if os.path.exists(processed_file):
        with open(processed_file, "r") as f:
            processed = json.load(f)
    else:
        processed = []

    if tx_id in processed:
        logger.info(f"Транзакция {tx_id} уже обработана")
        return jsonify({'status': 'already processed'}), 200

    # Начисление баланса
    users = load_users()
    if user_id not in users:
        users[user_id] = {"balance": 0}
    users[user_id]['balance'] = users[user_id].get('balance', 0) + amount
    save_users(users)

    processed.append(tx_id)
    with open(processed_file, "w") as f:
        json.dump(processed, f)

    send_notification(user_id, f"✅ Оплата {amount} FC получена! Баланс пополнен.")
    return jsonify({'status': 'ok'}), 200

# === ВЕБХУК TELEGRAM ===
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    logger.info(f"Получено обновление: {json_str}")
    try:
        update = telebot.types.Update.de_json(json_str)
        logger.info(f"Обновление распарсено: {update}")
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
    return '!', 200

# === ЗДОРОВЬЕ ===
@app.route('/')
def index():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
