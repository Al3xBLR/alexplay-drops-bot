import requests
import os
import re

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("❌ ОШИБКА: Не найдены необходимые секреты!")
    exit(1)

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
            print(f"✅ Отправлено в {chat_id}")
            return True
        else:
            print(f"❌ Ошибка Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка сети: {e}")
        return False

# === 1. ПРОВЕРКА EPIC GAMES (Прямой API) ===
def check_epic():
    print("🔍 Проверяем Epic Games...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        
        free_games = []
        for el in elements:
            if not isinstance(el, dict): continue
            price_info = el.get("price", {}).get("totalPrice", {}) or {}
            if price_info.get("discountPrice", 999999) == 0:
                free_games.append(el)
        return free_games
    except Exception as e:
        print(f"⚠️ Ошибка Epic API: {e}")
        return []

# === 2. ПРОВЕРКА ОСТАЛЬНЫХ ПЛОЩАДОК (Steam, GOG, Amazon, PS, Xbox через Reddit) ===
def check_other_platforms():
    print("🔍 Проверяем Steam, GOG, Amazon, PS, Xbox...")
    try:
        # Настоящий браузерный User-Agent, чтобы Reddit не блокировал запрос
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        
        subreddits = ["FreeGameFindings", "FreeGamesOnSteam"]
        freebies = []
        
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                posts = r.json().get("data", {}).get("children", [])
                for post in posts:
                    title = post["data"]["title"]
                    link = "https://reddit.com" + post["data"]["permalink"]
                    
                    # Ищем ключевые слова (free, 100%, giveaway, раздача)
                    if re.search(r'\b(free|giveaway|100%|раздача)\b', title, re.IGNORECASE):
                        # Убираем лишние теги в начале названия, например [EPIC] или [Steam]
                        clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                        # Добавляем только если такой ссылки еще нет (защита от дублей)
                        if not any(item['link'] == link for item in freebies):
                            freebies.append({"title": clean_title, "link": link})
                            
        # Возвращаем топ-6 свежих раздач
        return freebies[:6]
    except Exception as e:
        print(f"⚠️ Ошибка Reddit API: {e}")
        return []

# === ГЛАВНАЯ ФУНКЦИЯ ===
def main():
    print("🚀 Запуск полного сканирования халявы...")
    
    epic_games = check_epic()
    other_freebies = check_other_platforms()
    
    if not epic_games and not other_freebies:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Тишина в эфире!</b>\n\nСегодня крупных раздач не найдено. Но мы продолжаем следить 24/7! 🔔\n\nСледи за обновлениями в @AlexPlayDrops")
        return

    # ==========================================
    # ФОРМИРОВАНИЕ ПОСТА ДЛЯ @AlexPlayDrops
    # ==========================================
    drops_msg = "🔥 <b>ГЛОБАЛЬНЫЙ СБОР ХАЛЯВЫ!</b>\n\n"
    
    # Блок Epic Games
    if epic_games:
        drops_msg += "🟣 <b>EPIC GAMES:</b>\n"
        for i, g in enumerate(epic_games[:3], 1):
            title = g.get("title", "Игра")
            price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
            drops_msg += f"  {i}. <b>{title}</b> <i>(было {price})</i>\n"
        drops_msg += f"🔗 <b>Забрать:</b> https://store.epicgames.com/ru/free-games\n\n"
    else:
        drops_msg += "🟣 <b>EPIC GAMES:</b>\n  <i>Сейчас нет активных раздач.</i>\n\n"
        
    # Блок Остальные платформы
    if other_freebies:
        drops_msg += "🟢 <b>STEAM, GOG, AMAZON, PS, XBOX:</b>\n"
        for i, item in enumerate(other_freebies, 1):
            drops_msg += f"  {i}. <b>{item['title']}</b>\n"
            drops_msg += f"     🔗 <a href='{item['link']}'>Ссылка на раздачу</a>\n\n"
    else:
        drops_msg += "🟢 <b>STEAM, GOG, AMAZON, PS, XBOX:</b>\n  <i>Свежих раздач пока нет, но мы мониторим!</i>\n\n"
            
    drops_msg += "⏰ <i>Раздачи ограничены по времени! Забирай, пока не поздно.</i>\n\n"
    drops_msg += "🌟 <i>Больше новостей в @AlexPlayHub</i>"
    
    # ==========================================
    # ФОРМИРОВАНИЕ ПОСТА ДЛЯ @AlexPlayHub
    # ==========================================
    hub_msg = "🎁 <b>Свежий сбор халявы со всех площадок!</b>\n\n"
    hub_msg += "Epic Games, Steam, GOG, Amazon Prime и консоли.\n\n"
    hub_msg += "👉 <b>Подробный список и прямые ссылки уже в канале:</b>\n"
    hub_msg += " @AlexPlayDrops\n\n"
    hub_msg += "💬 <i>Какую игру заберешь сегодня? Пиши в комменты!</i>"
    
    # === ОТПРАВКА ===
    send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
    send_to_telegram(HUB_CHANNEL_ID, hub_msg)
    print("✅ Публикация завершена!")

if __name__ == "__main__":
    main()
