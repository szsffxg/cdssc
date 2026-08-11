import os
import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
from pyCryptoPayAPI import pyCryptoPayAPI

# --- ИМПОРТ ФУНКЦИЙ ИЗ SUPABASE ---
from db_supabase import (
    save_user,
    get_all_users,
    load_subscriptions_from_db,
    save_subscription,
    delete_subscription,
    is_subscribed as db_is_subscribed
)

load_dotenv()

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"✅ Токен загружен: {'ДА' if BOT_TOKEN else 'НЕТ'}")
if not BOT_TOKEN:
    logging.error("❌ Токен не найден! Проверьте переменную BOT_TOKEN.")
    exit(1)

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", 0))
PRICE_1 = int(os.getenv("PRICE_1_MONTH", 300))
PRICE_3 = int(os.getenv("PRICE_3_MONTH", 600))
PRICE_6 = int(os.getenv("PRICE_6_MONTH", 1000))

CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

# Создаём клиент Crypto Pay (синхронный)
crypto = pyCryptoPayAPI(CRYPTO_TOKEN)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Глобальная переменная для подписок
subscriptions = {}

def load_subscriptions():
    """Загружает подписки из Supabase в глобальную переменную"""
    global subscriptions
    subscriptions = load_subscriptions_from_db()


# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)  # Сохраняем в Supabase
    
    if db_is_subscribed(user_id, subscriptions):
        await update.message.reply_text(
            "✅ <b>У вас есть активная подписка!</b>\n\n"
            "📡 Gifts Intelligence — уже открыт\n"
            "🔍 NFT-Tracker — поиск владельцев подарков\n\n",
            parse_mode="HTML"
        )
        return
    
    text = (
        "💎 <b>Подписка на NFT-сигналы</b>\n\n"
        "Что вы получаете:\n"
        "📡 <b>Gifts Intelligence</b> — арбитражные сигналы по NFT-подаркам (Portals)\n"
        "🔍 <b>NFT-Tracker</b> — поиск владельцев подарков по модели, фону, номеру \n\n"
        "⚠️ <b>Дисклеймер:</b> Не финансовый совет. Все решения — на ваш риск\n\n"
        "💰 <b>Стоимость:</b>\n"
        "1 месяц — 300 ⭐ / 5 USDT\n"
        "3 месяца — 600 ⭐ / 10 USDT\n"
        "6 месяцев — 1000 ⭐ / 17 USDT\n\n"
        "Выберите способ оплаты:"
    )
    
    keyboard = [
        [InlineKeyboardButton("⭐ Telegram Stars", callback_data="pay_stars")],
        [InlineKeyboardButton("₿ Crypto Pay (USDT/TON)", callback_data="pay_crypto")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)


# --- КНОПКА НАЗАД (С УДАЛЕНИЕМ ИНВОЙСА) ---
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Удаляем сообщение с инвойсом, если оно было сохранено
    invoice_message_id = context.user_data.get('invoice_message_id')
    if invoice_message_id:
        try:
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=invoice_message_id
            )
            context.user_data['invoice_message_id'] = None
        except Exception as e:
            logger.error(f"Не удалось удалить инвойс: {e}")
    
    if db_is_subscribed(user_id, subscriptions):
        await query.edit_message_text(
            "✅ <b>У вас есть активная подписка!</b>\n\n"
            "📡 Gifts Intelligence — уже открыт\n"
            "🔍 NFT-Tracker — поиск владельцев подарков\n\n",
            parse_mode="HTML"
        )
        return
    
    text = (
        "💎 <b>Подписка на NFT-сигналы</b>\n\n"
        "Что вы получаете:\n"
        "📡 <b>Gifts Intelligence</b> — арбитражные сигналы по NFT-подаркам\n"
        "🔍 <b>NFT-Tracker</b> — поиск владельцев подарков\n\n"
        "⚠️ <b>Дисклеймер:</b> Не финансовый совет. Все решения — на ваш риск\n\n"
        "💰 <b>Стоимость:</b>\n"
        "1 месяц — 300 ⭐ / 5 USDT\n"
        "3 месяца — 600 ⭐ / 10 USDT\n"
        "6 месяцев — 1000 ⭐ / 17 USDT\n\n"
        "Выберите способ оплаты:"
    )
    
    keyboard = [
        [InlineKeyboardButton("⭐ Telegram Stars", callback_data="pay_stars")],
        [InlineKeyboardButton("₿ Crypto Pay (USDT/TON)", callback_data="pay_crypto")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)


# --- ВЫБОР СПОСОБА ОПЛАТЫ ---
async def choose_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "pay_stars":
        keyboard = [
            [InlineKeyboardButton(f"1 месяц — {PRICE_1} ⭐", callback_data="buy_1")],
            [InlineKeyboardButton(f"3 месяца — {PRICE_3} ⭐", callback_data="buy_3")],
            [InlineKeyboardButton(f"6 месяцев — {PRICE_6} ⭐", callback_data="buy_6")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "⭐ <b>Оплата Telegram Stars</b>\n\n"
            "Выберите тариф:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "pay_crypto":
        keyboard = [
            [InlineKeyboardButton("1 месяц — 5 USDT", callback_data="crypto_1")],
            [InlineKeyboardButton("3 месяца — 10 USDT", callback_data="crypto_3")],
            [InlineKeyboardButton("6 месяцев — 17 USDT", callback_data="crypto_6")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
        ]
        await query.edit_message_text(
            "₿ <b>Оплата криптовалютой</b>\n\n"
            "Выберите тариф:\n"
            "💳 USDT (TRC-20) или TON",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# --- ПОКУПКА ЧЕРЕЗ STARS (С СОХРАНЕНИЕМ ID ИНВОЙСА) ---
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "buy_1":
        price = PRICE_1
        days = 30
        label = "1 месяц"
    elif data == "buy_3":
        price = PRICE_3
        days = 90
        label = "3 месяца"
    elif data == "buy_6":
        price = PRICE_6
        days = 180
        label = "6 месяцев"
    else:
        return
    
    try:
        sent_message = await context.bot.send_invoice(
            chat_id=user_id,
            title=f"Подписка на сигналы — {label}",
            description="Доступ к сигнальному каналу + NFT-Tracker",
            payload=f"sub_{days}_{user_id}",
            provider_token="",
            currency="XTR",
            prices=[{"label": label, "amount": price}],
            start_parameter="sub",
            need_name=False,
            need_phone_number=False,
            need_email=False
        )
        
        context.user_data['invoice_message_id'] = sent_message.message_id
        
    except Exception as e:
        logger.error(f"Ошибка создания счёта: {e}")
        await query.edit_message_text("❌ Ошибка создания счёта. Попробуйте позже.")


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    payload = update.message.successful_payment.invoice_payload
    
    parts = payload.split("_")
    days = int(parts[1])
    
    expires = datetime.now() + timedelta(days=days)
    
    # --- СОХРАНЯЕМ В SUPABASE ---
    save_subscription(user_id, expires, "stars")
    
    # Обновляем глобальную переменную
    global subscriptions
    subscriptions[user_id] = expires
    
    save_user(user_id)
    
    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            creates_join_request=False
        )
        
        await update.message.reply_text(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка активна до {expires.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📡 <b>Gifts Intelligence:</b>\n"
            f"{invite_link.invite_link}\n\n"
            f"🔍 <b>NFT-Tracker</b> — поиск владельцев подарков\n"
            f"👉 @fyvfhvfhyfbot\n\n"
            f"🎉 Спасибо за подписку!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка создания ссылки: {e}")
        await update.message.reply_text(
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"Подписка активна до {expires.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"⚠️ Напишите @skillell для получения доступа.",
            parse_mode="HTML"
        )


# --- ПОКУПКА ЧЕРЕЗ CRYPTO PAY (СИНХРОННАЯ) ---
async def crypto_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "crypto_1":
        days = 30
        price = 5
        label = "1 месяц"
    elif data == "crypto_3":
        days = 90
        price = 10
        label = "3 месяца"
    elif data == "crypto_6":
        days = 180
        price = 17
        label = "6 месяцев"
    else:
        return
    
    try:
        invoice = crypto.create_invoice(
            asset="USDT",
            amount=price,
            description=f"Подписка на NFT-сигналы — {label}",
            hidden_message=f"Спасибо за подписку! Ваш ID: {user_id}",
            #paid_btn_name="openChannel",
            #paid_btn_url="https://t.me/твой_канал"
        )
        
        if not invoice or 'invoice_id' not in invoice:
            raise Exception("Не удалось создать инвойс")
        
        context.user_data['crypto_invoice_id'] = invoice['invoice_id']
        context.user_data['crypto_days'] = days
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить", url=invoice['pay_url'])],
            [InlineKeyboardButton("✅ Я оплатил", callback_data=f"crypto_check_{invoice['invoice_id']}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")],
        ])
        
        await query.edit_message_text(
            f"₿ <b>Оплата криптовалютой</b>\n\n"
            f"Сумма: {price} USDT\n"
            f"Период: {label}\n\n"
            f"1. Нажмите «Оплатить»\n"
            f"2. Оплатите через @CryptoBot\n"
            f"3. Вернитесь и нажмите «Я оплатил»",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания инвойса Crypto Pay: {e}")
        await query.edit_message_text(f"❌ Ошибка создания счёта: {str(e)}")


# --- ПРОВЕРКА ОПЛАТЫ CRYPTO PAY (СИНХРОННАЯ) ---
async def crypto_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    invoice_id = int(query.data.split("_")[2])
    days = context.user_data.get('crypto_days', 30)
    
    try:
        invoice = crypto.get_invoices(invoice_id=invoice_id)
        
        if invoice and invoice.get('status') == 'paid':
            expires = datetime.now() + timedelta(days=days)
            
            # --- СОХРАНЯЕМ В SUPABASE ---
            save_subscription(user_id, expires, "crypto")
            
            # Обновляем глобальную переменную
            global subscriptions
            subscriptions[user_id] = expires
            
            save_user(user_id)
            
            try:
                invite_link = await context.bot.create_chat_invite_link(
                    chat_id=CHANNEL_ID,
                    member_limit=1,
                    creates_join_request=False
                )
                await query.edit_message_text(
                    f"✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"Подписка активна до {expires.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"📡 <b>Gifts Intelligence:</b>\n"
                    f"{invite_link.invite_link}\n\n"
                    f"🔍 <b>NFT-Tracker</b>\n"
                    f"👉 @fyvfhvfhyfbot\n\n"
                    f"🎉 Спасибо за подписку!",
                    parse_mode="HTML"
                )
            except Exception as e:
                await query.edit_message_text(
                    f"✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"Подписка активна до {expires.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"⚠️ Напишите @skillell для получения доступа.",
                    parse_mode="HTML"
                )
        else:
            await query.edit_message_text(
                "❌ <b>Платеж не найден</b>\n\n"
                "Убедитесь, что оплата прошла, и нажмите «Я оплатил» снова.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка проверки инвойса: {e}")
        await query.edit_message_text(f"❌ Ошибка проверки: {str(e)}")


# --- АДМИН ---
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    active = sum(1 for exp in subscriptions.values() if exp > datetime.now())
    total = len(subscriptions)
    
    await update.message.reply_text(
        f"📊 <b>Статистика</b>\n"
        f"Всего подписок: {total}\n"
        f"Активных: {active}\n"
        f"Истекло: {total - active}",
        parse_mode="HTML"
    )


# --- ПЕРЕСЫЛКА СООБЩЕНИЙ ---
async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    text = update.message.text
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 <b>Новое сообщение</b>\n"
             f"👤 {user.first_name} (@{user.username or 'нет'})\n"
             f"🆔 {user.id}\n\n"
             f"📝 {text}",
        parse_mode="HTML"
    )


# --- ОТВЕТ ПОЛЬЗОВАТЕЛЮ ---
async def answer_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text("❌ Формат: /answer ID_пользователя Текст ответа")
        return
    
    try:
        user_id = int(parts[1])
        reply_text = parts[2]
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📩 <b>Ответ от администратора:</b>\n\n{reply_text}",
            parse_mode="HTML"
        )
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID пользователя")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# --- РАССЫЛКА ---
async def send_to_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Доступ запрещён")
        return
    
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Формат: /send Текст сообщения")
        return
    
    message_text = parts[1]
    
    # --- ПОЛУЧАЕМ ПОЛЬЗОВАТЕЛЕЙ ИЗ SUPABASE ---
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("❌ Нет пользователей")
        return
    
    await update.message.reply_text(f"📨 Отправляю сообщение {len(users)} пользователям...")
    
    success = 0
    fail = 0
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"{message_text}",
                parse_mode="HTML"
            )
            success += 1
            await asyncio.sleep(0.05)  # Небольшая задержка, чтобы не спамить
        except Exception:
            fail += 1
    
    await update.message.reply_text(
        f"✅ Готово!\n"
        f"📨 Доставлено: {success}\n"
        f"❌ Ошибок: {fail}"
    )


# --- ЗАПУСК ---
def main():
    # Загружаем подписки из Supabase
    load_subscriptions()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("answer", answer_user))
    application.add_handler(CommandHandler("send", send_to_all))
    application.add_handler(CallbackQueryHandler(buy_handler, pattern="buy_"))
    application.add_handler(CallbackQueryHandler(choose_payment, pattern="pay_"))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern="back_to_start"))
    application.add_handler(CallbackQueryHandler(crypto_buy, pattern="crypto_"))
    application.add_handler(CallbackQueryHandler(crypto_check, pattern="crypto_check_"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))
    
    logger.info("Бот запущен!")
    
    # Удаляем вебхук перед запуском
    application.bot.delete_webhook(drop_pending_updates=True)
    
    application.run_polling()


if __name__ == "__main__":
    main()
