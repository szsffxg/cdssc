import os
import logging
import asyncio
import threading
from flask import Flask, jsonify

# Импортируем функцию main() из вашего bot.py
from bot import main as bot_main

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def root():
    return "✅ Бот работает!", 200

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

# --- Функция для запуска Flask во втором потоке ---
def run_flask():
    """Запускает Flask-сервер в отдельном потоке."""
    port = int(os.getenv('PORT', 10000))
    logger.info(f"🚀 Запуск Flask-сервера на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    # 1. Запускаем Flask в фоновом потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask-сервер запущен в фоновом потоке")

    # 2. Запускаем бота в ГЛАВНОМ потоке
    logger.info("🤖 Запуск бота в главном потоке...")
    try:
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка при запуске бота: {e}")
