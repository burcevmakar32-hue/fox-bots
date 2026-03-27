from flask import Flask
import os

FOXY_SERVICE_ID = "НОВЫЙ_ID_СЕРВИСА"   # вставь сюда новый ID
FOXY_SECRET_KEY = "95ef5c3a12ea8616f769e6490ee84f740d31a637201a6d5d"
FOXY_BOT_LINK = "https://t.me/foxcoingame_bot/app"

app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Bot is running!"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
