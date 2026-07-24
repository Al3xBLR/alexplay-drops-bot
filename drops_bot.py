import requests
import os
from datetime import datetime

# Берем данные из настроек GitHub (это самый надежный способ)
BOT_TOKEN = os.environ.get("8802598546:AAFYr68ro4qTxr_CQ_VPFr1eHUJwhDpwTQg")
CHAT_ID = os.environ.get("426792094")

# Проверка: если данные не загрузились, скрипт сразу об этом скажет в логах
if not BOT_TOKEN or not CHAT_ID:
    print("❌ ОШИБКА: Не найдены BOT_TOKEN или CHAT_ID в настройках GitHub!")
    exit(1)

EPIC_API = "https://store-site-backend-static.ak.epicgames.com/graphql"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Запрос к Epic Games на поиск бесплатных игр
QUERY = """
query searchQuery {
  Catalog {
    searchStore(locale: "ru", count: 20, category: "bundles/0", freeGame: true) {
      elements {
        title
        urlSlug
        price {
          totalPrice {
            fmtPrice(locale: "ru-RU") { originalPrice }
          }
        }
      }
    }
  }
}
"""

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
        r = requests.post(EPIC_API, json={"query": QUERY}, timeout=15)
        r.raise_for_status() # Проверка на ошибки HTTP
        
        games = r.json()["data"]["Catalog"]["searchStore"]["elements"]
        
        if not games:
            send_telegram("🤖 <b>Внимание:</b>\nСегодня новых бесплатных игр в Epic Games нет. Но скоро будут!")
            return
        
        msg = "🎁 <b>Свежая халява в Epic Games!</b>\n\n"
        for g in games[:5]: # Берем максимум 5 игр, если их вдруг несколько
            title = g["title"]
            slug = g["urlSlug"]
            price = g["price"]["totalPrice"]["fmtPrice"]["originalPrice"]
            link = f"https://store.epicgames.com/ru/p/{slug}"
            msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n🔗 {link}\n\n"
        
        msg += "⏰ <i>Забирай, пока дают!</i>"
        send_telegram(msg)
        
    except Exception as e:
        error_msg = f"⚠️ <b>Ошибка при проверке Epic Games:</b>\n<code>{str(e)}</code>"
        send_telegram(error_msg)
        print(f"❌ Ошибка выполнения: {e}")

if __name__ == "__main__":
    check_free_games()
