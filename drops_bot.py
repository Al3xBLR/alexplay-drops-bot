import requests
import time
from datetime import datetime

# ===== ЗАМЕНИ ЭТИ 3 ЗНАЧЕНИЯ НА СВОИ =====
BOT_TOKEN = "8802598546:AAFYr68ro4qTxr_CQ_VPFr1eHUJwhDpwTQg"   # Токен от BotFather
CHAT_ID = "426792094"                  # Твой chat_id
# =========================================

EPIC_API = "https://store-site-backend-static.ak.epicgames.com/graphql"
TELEGRAM_URL = f"https://api.telegram.org/bot8802598546:AAFYr68ro4qTxr_CQ_VPFr1eHUJwhDpwTQg/sendMessage"

# GraphQL-запрос к Epic Games
QUERY = """
query searchQuery {
  Catalog {
    searchStore(locale: "ru", count: 20, category: "bundles/0", freeGame: true) {
      elements {
        title
        urlSlug
        seller { name }
        price {
          totalPrice {
            discountPrice
            originalPrice
            fmtPrice(locale: "ru-RU") { originalPrice, discountPrice }
          }
        }
      }
    }
  }
}
"""

def send_telegram(text):
    requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

def check_free_games():
    try:
        r = requests.post(EPIC_API, json={"query": QUERY}, timeout=15)
        games = r.json()["data"]["Catalog"]["searchStore"]["elements"]
        
        if not games:
            send_telegram("🤖 Сегодня бесплатных игр в Epic нет.")
            return
        
        msg = "🎁 <b>Свежая халява в Epic Games!</b>\n\n"
        for g in games[:5]:
            title = g["title"]
            slug = g["urlSlug"]
            price = g["price"]["totalPrice"]["fmtPrice"]["originalPrice"]
            link = f"https://store.epicgames.com/ru/p/{slug}"
            msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n🔗 {link}\n\n"
        
        msg += "⏰ Забирай, пока дают!"
        send_telegram(msg)
        print(f"[{datetime.now()}] Уведомление отправлено")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    check_free_games()
