import requests
import os
from datetime import datetime

# Безопасно берем данные из защищенных настроек GitHub
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("❌ ОШИБКА: Не найдены BOT_TOKEN или CHAT_ID в секретах GitHub!")
    exit(1)

# НОВЫЙ, стабильный endpoint специально для бесплатных игр Epic Games
EPIC_API = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram(text):
    try:
        response = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if response.status_code == 200:
            print("✅ Сообщение успешно отправлено в Telegram!")
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")

def check_free_games():
    print("🔍 Проверяем Epic Games Store...")
    try:
        # Добавляем заголовок, чтобы Epic Games не блокировал запрос как от бота
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(EPIC_API, headers=headers, timeout=15)
        r.raise_for_status()
        
        data = r.json()
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        
        # Фильтруем только те игры, у которых есть активная или предстоящая акция
        free_games = []
        for el in elements:
            promotions = el.get("promotions", {}).get("promotionalOffers", [])
            upcoming = el.get("promotions", {}).get("upcomingPromotionalOffers", [])
            if promotions or upcoming:
                free_games.append(el)
        
        if not free_games:
            send_telegram("🤖 <b>Внимание:</b>\nСегодня новых бесплатных игр в Epic Games нет. Но скоро будут!")
            return
        
        msg = "🎁 <b>Свежая халява в Epic Games!</b>\n\n"
        for g in free_games[:5]: # Берем топ-5 актуальных предложений
            title = g.get("title")
            slug = g.get("productSlug") or g.get("urlSlug")
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0")
            link = f"https://store.epicgames.com/ru/p/{slug}" if slug else "https://store.epicgames.com/ru/"
            msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n🔗 {link}\n\n"
        
        msg += "⏰ <i>Забирай, пока дают!</i>"
        send_telegram(msg)
        print("✅ Проверка завершена успешно!")
        
    except Exception as e:
        error_msg = f"⚠️ <b>Ошибка при проверке Epic Games:</b>\n<code>{str(e)}</code>"
        send_telegram(error_msg)
        print(f"❌ Ошибка выполнения: {e}")

if __name__ == "__main__":
    check_free_games()
