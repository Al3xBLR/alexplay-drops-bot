import requests
import os

# Безопасно берем данные из защищенных настроек GitHub
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    print("❌ ОШИБКА: Не найдены BOT_TOKEN или CHAT_ID в секретах GitHub!")
    exit(1)

# Стабильный публичный адрес Epic Games для бесплатных игр
EPIC_API = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram(text):
    try:
        response = requests.post(TELEGRAM_URL, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        if response.status_code == 200:
            print("✅ Сообщение успешно отправлено в Telegram!")
        else:
            print(f"❌ Ошибка Telegram: {response.status_code}, {response.text}")
    except Exception as e:
        print(f" Ошибка отправки: {e}")

def check_free_games():
    print("🔍 Проверяем Epic Games Store...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(EPIC_API, headers=headers, timeout=15)
        r.raise_for_status()
        
        data = r.json()
        
        elements = []
        if isinstance(data, dict) and data.get("data") is not None:
            catalog = data["data"].get("Catalog", {}) or {}
            search_store = catalog.get("searchStore", {}) or {}
            elements = search_store.get("elements", []) or []
        
        free_games = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            
            price_info = el.get("price", {}).get("totalPrice", {}) or {}
            discount_price = price_info.get("discountPrice", 999999)
            
            if discount_price == 0:
                free_games.append(el)
        
        if not free_games:
            send_telegram(" <b>Внимание:</b>\nСегодня новых бесплатных игр в Epic Games нет. Но скоро будут!")
            return
        
        msg = "🎁 <b>Свежая халява в Epic Games!</b>\n\n"
        for g in free_games[:5]:
            title = g.get("title", "Неизвестная игра")
            
            # Умный поиск правильной ссылки (используем разные варианты slug)
            slug = g.get("productSlug") or g.get("urlSlug") or g.get("catalogNs", {}).get("mappings", [{}])[0].get("pageSlug", "")
            
            if slug:
                slug = slug.strip('/')
                link = f"https://store.epicgames.com/ru/p/{slug}"
            else:
                # Если slug не подошел, делаем ссылку на поиск по названию
                search_title = title.replace(" ", "+")
                link = f"https://store.epicgames.com/ru/search?q={search_title}"
            
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
            
            msg += f"🎮 <b>{title}</b>\n💰 Было: {price}\n🔗 {link}\n\n"
        
        msg += "⏰ <i>Забирай, пока дают!</i>\n\n<i>Если ссылка не открывается, просто найди игру по названию в магазине Epic Games</i>"
        send_telegram(msg)
        print("✅ Проверка завершена успешно!")
        
    except Exception as e:
        error_msg = f"⚠️ <b>Ошибка при проверке Epic Games:</b>\n<code>{str(e)}</code>"
        send_telegram(error_msg)
        print(f"❌ Ошибка выполнения: {e}")

if __name__ == "__main__":
    check_free_games()
