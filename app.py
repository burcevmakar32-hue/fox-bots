import os
import json
import logging
import hmac
import hashlib
from flask import Flask, request, jsonify
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === КОНФИГУРАЦИЯ (берём из переменных окружения) ===
BOT_TOKEN = os.environ.get("8743642269:AAGaXTL80peI1yBQh7XzTCXum2GWOS1fE_4")                     # токен Telegram бота
FOXY_SERVICE_ID = os.environ.get("6b95aa398861")         # ID твоего сервиса Foxy
FOXY_SECRET_KEY = os.environ.get("95ef5c3a12ea8616f769e6490ee84f740d31a637201a6d5d")         # секретный ключ (95ef5c3a...)
FOXY_BOT_LINK = "https://t.me/foxcoingame_bot/app"          # ссылка на приложение Foxy

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

# === ОТПРАВКА УВЕДОМЛЕНИЙ В TELEGRAM (через API) ===
def send_notification(chat_id, text):
    try:
        bot.send_message(chat_id, text)
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

# === КОМАНДЫ БОТА ===
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
    # Сумма товара — 100 FC
    price = 100
    startapp = f"service_{FOXY_SERVICE_ID}__user_{user_id}__sum_{price}__lock_1"
    payment_url = f"{FOXY_BOT_LINK}?startapp={startapp}&topup_sum={price}&topup_lock=1"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💎 Купить 100 FC", url=payment_url))
    bot.reply_to(message, "🛒 Магазин:\n100 FC = 100 единиц", reply_markup=keyboard)

# === ОБРАБОТЧИК CALLBACK ОТ FOXY COMPANY ===
@app.route('/callback', methods=['POST'])
def callback():
    # Получаем данные в формате JSON
    data = request.get_json()
    if not data:
        logging.warning("Callback: нет JSON")
        return jsonify({'error': 'Invalid request'}), 400

    logging.info(f"Callback получен: {data}")

    # Ожидаем, что Foxy пришлёт поля: tx_id, user_id, amount, sign
    tx_id = data.get('tx_id')
    user_id = data.get('user_id')
    amount = data.get('amount')
    sign = data.get('sign')

    if not all([tx_id, user_id, amount, sign]):
        logging.warning("Не хватает полей в callback")
        return jsonify({'error': 'Missing fields'}), 400

    # Приводим типы
    user_id = str(user_id)
    amount = int(amount)

    # Проверка подписи (HMAC-SHA256)
    # Формируем строку для подписи: tx_id:user_id:amount
    message = f"{tx_id}:{user_id}:{amount}"
    expected_sign = hmac.new(
        FOXY_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sign, sign):
        logging.error(f"Неверная подпись для tx {tx_id}")
        return jsonify({'error': 'Invalid signature'}), 403

    # Проверяем, не обработана ли уже эта транзакция
    users = load_users()
    # Для простоты будем хранить список обработанных tx в отдельном файле или в users.json
    # Добавим поле processed_tx в users (или отдельный файл)
    processed_file = "processed_tx.json"
    if os.path.exists(processed_file):
        with open(processed_file, "r") as f:
            processed = json.load(f)
    else:
        processed = []
    if tx_id in processed:
        logging.info(f"Транзакция {tx_id} уже обработана")
        return jsonify({'status': 'already processed'}), 200

    # Начисляем баланс
    if user_id not in users:
        users[user_id] = {"balance": 0}
    users[user_id]['balance'] = users[user_id].get('balance', 0) + amount
    save_users(users)

    # Сохраняем ID транзакции
    processed.append(tx_id)
    with open(processed_file, "w") as f:
        json.dump(processed, f)

    # Отправляем пользователю уведомление в Telegram
    send_notification(user_id, f"✅ Оплата на сумму {amount} FC получена! Баланс пополнен.")

    return jsonify({'status': 'ok'}), 200

# === ВЕБХУК ДЛЯ TELEGRAM (принимает обновления) ===
@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200

# === ЗДОРОВЬЕ ===
@app.route('/')
def index():
    return "✅ Bot is running!"

# === ЗАПУСК ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
