import requests
import os

# Безопасно берем данные из защищенных настроек GitHub
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")  # Твой личный ID (на случай ошибок)
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")  # ID канала @AlexPlayDrops
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")      # ID канала @AlexPlayHub

# Проверка: если не хватает хотя бы одного ключа, останавливаемся
if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("❌ ОШИБКА: Не найдены необходимые секреты в настройках GitHub!")
    exit(1)

# Адреса API
EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_to_telegram(chat_id, text):
    """Функция отправки сообщения в Telegram"""
    try:
        response = requests.post(TELEGRAM_URL, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
        if response.status_code == 200:
            print(f"✅ Успешно отправлено в канал {chat_id}")
            return True
        else:
            print(f" Ошибка Telegram {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка сети при отправке: {e}")
        return False

def check_free_games():
    """Основная функция проверки и публикации"""
    print("🔍 Начинаем проверку Epic Games Store...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(EPIC_API, headers=headers, timeout=15)
        r.raise_for_status()
        
        data = r.json()
        
        # Безопасное извлечение списка игр
        elements = []
        if isinstance(data, dict) and data.get("data"):
            elements = data["data"].get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        
        # Фильтруем только те, где цена со скидкой равна 0 (бесплатные)
        free_games = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            price_info = el.get("price", {}).get("totalPrice", {}) or {}
            if price_info.get("discountPrice", 999999) == 0:
                free_games.append(el)
        
        main_link = "https://store.epicgames.com/ru/free-games"
        
        # Если бесплатных игр сейчас нет
        if not free_games:
            no_games_msg = "🤖 <b>Тишина в эфире!</b>\n\n"
            no_games_msg += "Сегодня Epic Games не раздаёт новых игр.\n\n"
            no_games_msg += "Но мы продолжаем следить 24/7! 🔔\n"
            no_games_msg += "Следи за обновлениями в @AlexPlayDrops"
            send_to_telegram(DROPS_CHANNEL_ID, no_games_msg)
            return
        
        # ==========================================
        # ФОРМИРОВАНИЕ КРАСИВОГО ПОСТА ДЛЯ DROPS
        # ==========================================
        drops_msg = " <b>ВНИМАНИЕ! EPIC GAMES РАЗДАЕТ ИГРЫ БЕСПЛАТНО!</b>\n\n"
        
        for i, g in enumerate(free_games[:5], 1):
            title = g.get("title", "Неизвестная игра")
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
            drops_msg += f" <b>{i}. {title}</b>\n"
            drops_msg += f"💰 <i>Оригинальная цена:</i> {price}\n\n"
        
        drops_msg += "✅ <b>КАК ЗАБРАТЬ:</b>\n"
        drops_msg += "1️⃣ Перейди по ссылке\n"
        drops_msg += "2️⃣ Нажми «Получить»\n"
        drops_msg += "3️⃣ Игра останется в библиотеке навсегда!\n\n"
        
        drops_msg += f" <b>ЗАБРАТЬ ИГРЫ СЕЙЧАС:</b> {main_link}\n\n"
        drops_msg += "⏰ <i>Раздача заканчивается через 48 часов!</i>\n\n"
        drops_msg += " <i>Комментируй, какую игру ты заберешь первым</i>\n\n"
        drops_msg += "🌟 <b>Подпишись на @AlexPlayHub — там ты найдешь:</b>\n"
        drops_msg += "• Обзоры новых релизов\n"
        drops_msg += "• Секреты геймплея\n"
        drops_msg += "• Ретро-подборки\n\n"
        drops_msg += "💡 <i>Каждый четверг — новые раздачи, не пропусти!</i>"
        
        # ==========================================
        # ФОРМИРОВАНИЕ ПОСТА ДЛЯ HUB
        # ==========================================
        hub_msg = "🎁 <b>ЭТО ВАЖНО! EPIC GAMES РАЗДАЕТ ИГРЫ БЕСПЛАТНО</b>\n\n"
        
        for i, g in enumerate(free_games[:3], 1):
            title = g.get("title", "Неизвестная игра")
            hub_msg += f"{i}.  <b>{title}</b>\n"
        
        hub_msg += "\n🔥 <b>СРОЧНО ЗАБИРАЙ:</b>\n"
        hub_msg += "👉 @AlexPlayDrops\n\n"
        
        hub_msg += "⏰ <i>Раздача заканчивается через 48 часов!</i>\n\n"
        hub_msg += "💬 <i>Проголосуй в комментариях:</i>\n"
        hub_msg += "• Нравится ли тебе этот формат?\n"
        hub_msg += "• Что еще хочешь видеть в канале?\n\n"
        hub_msg += "🔔 <i>Включай уведомления, чтобы не пропустить следующую раздачу!</i>"
        
        # ==========================================
        # ОТПРАВКА В КАНАЛЫ
        # ==========================================
        success_drops = send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
        success_hub = send_to_telegram(HUB_CHANNEL_ID, hub_msg)
        
        if success_drops and success_hub:
            print("✅ Публикация в оба канала успешно завершена!")
        else:
            print("⚠️ Частичный успех — проверь, в какой канал не дошло сообщение")
        
    except Exception as e:
        error_msg = f"️ <b>Техническая ошибка бота:</b>\n<code>{str(e)}</code>\n\nАдминистратор уже уведомлен."
        send_to_telegram(CHAT_ID, error_msg)  # Отправляем отчет об ошибке тебе в личку
        print(f"❌ Критическая ошибка выполнения: {e}")

if __name__ == "__main__":
    check_free_games()
