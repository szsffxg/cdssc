import os
from datetime import datetime
from supabase import create_client, Client
from typing import Dict, List

# --- НАСТРОЙКА ПОДКЛЮЧЕНИЯ ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ SUPABASE_URL и SUPABASE_KEY должны быть заданы в переменных окружения!")

# Создаём клиент Supabase (синхронный)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ---
def save_user(user_id: int) -> None:
    """Сохраняет пользователя в базу, если его там нет"""
    try:
        # Проверяем, есть ли пользователь
        result = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if not result.data:
            # Если нет — добавляем
            supabase.table("users").insert({"user_id": user_id}).execute()
            print(f"✅ Пользователь {user_id} добавлен в базу")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения пользователя {user_id}: {e}")


def get_all_users() -> List[int]:
    """Возвращает список всех пользователей (для рассылки)"""
    try:
        result = supabase.table("users").select("user_id").execute()
        return [item['user_id'] for item in result.data]
    except Exception as e:
        print(f"⚠️ Ошибка получения списка пользователей: {e}")
        return []


# --- ФУНКЦИИ ДЛЯ РАБОТЫ С ПОДПИСКАМИ ---
def load_subscriptions_from_db() -> Dict[int, datetime]:
    """Загружает все подписки из базы"""
    subscriptions = {}
    try:
        result = supabase.table("subscriptions").select("user_id, expires_at").execute()
        for item in result.data:
            # Преобразуем строку в datetime
            expires_str = item['expires_at'].replace('Z', '+00:00')
            subscriptions[item['user_id']] = datetime.fromisoformat(expires_str)
        print(f"✅ Загружено {len(subscriptions)} подписок из базы")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки подписок: {e}")
    return subscriptions


def save_subscription(user_id: int, expires_at: datetime, tariff: str = 'month') -> None:
    """Сохраняет или обновляет подписку пользователя"""
    try:
        # Upsert: обновить или вставить
        supabase.table("subscriptions").upsert({
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
            "tariff": tariff,
            "updated_at": datetime.now().isoformat()
        }).execute()
        print(f"✅ Подписка для {user_id} сохранена до {expires_at}")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения подписки для {user_id}: {e}")


def delete_subscription(user_id: int) -> None:
    """Удаляет подписку пользователя (если нужно)"""
    try:
        supabase.table("subscriptions").delete().eq("user_id", user_id).execute()
        print(f"✅ Подписка для {user_id} удалена")
    except Exception as e:
        print(f"⚠️ Ошибка удаления подписки для {user_id}: {e}")


def is_subscribed(user_id: int, subscriptions: Dict[int, datetime]) -> bool:
    """Проверяет, активна ли подписка"""
    if user_id not in subscriptions:
        return False
    return subscriptions[user_id] > datetime.now()
