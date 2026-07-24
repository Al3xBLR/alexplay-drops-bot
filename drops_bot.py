import requests
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("❌ ОШИБКА: Не найдены BOT_TOKEN или CHAT_ID!")
    exit(1)

EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram(text):
    try:
        response = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if response.status_code == 200:
            print("✅ Сообщение отправлено!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

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
            send_telegram("🤖 <b>Внимание:</b>\nСегодня бесплатных игр в Epic Games нет.")
            return
        
        # УНИВЕРСАЛЬНАЯ ССЫЛКА - всегда работает!
        main_link = "https://store.epicgames.com/ru/free-games"
        
        msg = "🎁 <b>Свежая халява в Epic Games!</b>\n\n"
        for g in free_games[:5]:
            title = g.get("title", "Неизвестная игра")
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
            msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n"
        
        msg += f"\n <b>ЗАБРАТЬ ВСЕ ИГРЫ:</b> {main_link}"
        msg += "\n\n⏰ <i>Забирай, пока дают!</i>"
        send_telegram(msg)
        print("✅ Готово!")
        
    except Exception as e:
        send_telegram(f"⚠️ <b>Ошибка:</b>\n<code>{str(e)}</code>")
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    check_free_games()
