import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")  # Твой личный ID (для тестов)
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")  # ID канала @AlexPlayDrops
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")      # ID канала @AlexPlayHub

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("❌ ОШИБКА: Не найдены необходимые секреты!")
    exit(1)

EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_to_telegram(chat_id, text):
    try:
        response = requests.post(TELEGRAM_URL, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
        if response.status_code == 200:
            print(f"✅ Отправлено в канал {chat_id}")
            return True
        else:
            print(f"❌ Ошибка {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def check_free_games():
    print("🔍 Проверяем Epic Games...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(EPIC_API, headers=headers, timeout=15)
        r.raise_for_status()
        
        data = r.json()
        elements = []
        if isinstance(data, dict) and data.get("data"):
            elements = data["data"].get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        
        free_games = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            price_info = el.get("price", {}).get("totalPrice", {}) or {}
            if price_info.get("discountPrice", 999999) == 0:
                free_games.append(el)
        
        if not free_games:
            msg = "🤖 <b>Внимание:</b>\nСегодня бесплатных игр в Epic Games нет.\n\nНо мы продолжаем следить! 🔔"
            send_to_telegram(DROPS_CHANNEL_ID, msg)
            return
        
        main_link = "https://store.epicgames.com/ru/free-games"
        
        # Сообщение для канала @AlexPlayDrops
        drops_msg = "🚨 <b>НОВАЯ ХАЛЯВА В EPIC GAMES!</b>\n\n"
        for g in free_games[:5]:
            title = g.get("title", "Неизвестная игра")
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
            drops_msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n\n"
        
        drops_msg += f"<b>🔗 ЗАБРАТЬ ИГРЫ:</b> {main_link}\n\n"
        drops_msg += "⏰ <i>Забирай, пока дают!</i>\n\n"
        drops_msg += "<i>Подпишись на @AlexPlayHub — главные новости игр!</i>"
        
        # Сообщение для канала @AlexPlayHub (короче, просто новость)
        hub_msg = "🎁 <b>Epic Games раздают бесплатные игры!</b>\n\n"
        for g in free_games[:3]:
            title = g.get("title", "Неизвестная игра")
            hub_msg += f"• {title}\n"
        
        hub_msg += f"\n🔗 Все игры и инструкции в канале @AlexPlayDrops"
        
        # Отправляем в оба канала
        success_drops = send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
        success_hub = send_to_telegram(HUB_CHANNEL_ID, hub_msg)
        
        if success_drops and success_hub:
            print("✅ Публикация в каналах завершена!")
        else:
            print("⚠️ Частичный успех — проверь каналы")
        
    except Exception as e:
        error_msg = f"⚠️ <b>Ошибка при проверке Epic Games:</b>\n<code>{str(e)}</code>"
        send_to_telegram(CHAT_ID, error_msg)  # Отправляем ошибку тебе в личку
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_free_games()
