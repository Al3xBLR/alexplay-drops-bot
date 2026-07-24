import requests
import os
import re
from datetime import datetime
import random

# === НАСТРОЙКИ (Берем из безопасных секретов GitHub) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")
RAWG_API_KEY = os.environ.get("RAWG_API_KEY")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID, RAWG_API_KEY]):
    print("❌ ОШИБКА: Не найдены необходимые секреты! Проверь настройки GitHub.")
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
            print(f"✅ Успешно отправлено в {chat_id}")
            return True
        else:
            print(f"❌ Ошибка Telegram {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка сети при отправке: {e}")
        return False

# === РУБРИКА 1 и 3: ИГРА ДНЯ + ФАКТ ДНЯ (Живые данные из RAWG.io НА РУССКОМ) ===
def get_rawg_game_and_fact():
    print("🔍 Запрашиваем игру дня из RAWG.io...")
    try:
        day_of_year = datetime.now().timetuple().tm_yday
        page = (day_of_year % 150) + 1 
        
        # ДОБАВЛЕН ПАРАМЕТР &language=ru для получения русского текста
        url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&language=ru&ordering=-added&dates=1990-01-01,2025-12-31&page={page}&page_size=3"
        headers = {"User-Agent": "AlexPlayBot/1.0"}
        
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        games = r.json().get("results", [])
        
        if not games:
            raise Exception("Не удалось получить игры из RAWG")
            
        game = random.choice(games)
        
        # Также запрашиваем детали на русском
        detail_url = f"https://api.rawg.io/api/games/{game['id']}?key={RAWG_API_KEY}&language=ru"
        detail_r = requests.get(detail_url, headers=headers, timeout=10)
        detail = detail_r.json()
        
        title = game.get("name", "Неизвестная игра")
        year = game.get("released", "Неизвестный год")[:4] if game.get("released") else "Неизвестный год"
        rating = game.get("rating", "N/A")
        
        developers = detail.get("developers", [])
        dev_name = developers[0]["name"] if developers else "Неизвестный разработчик"
        
        desc_raw = detail.get("description_raw", "Описание отсутствует.")
        desc_clean = re.sub(r'<[^>]+>', '', desc_raw)
        desc = (desc_clean[:250] + '...') if len(desc_clean) > 250 else desc_clean
        
        # Формируем пост Игры дня
        game_msg = " <b>ИГРА ДНЯ</b>\n\n"
        game_msg += f"🎮 <b>{title}</b> <i>({year})</i>\n"
        game_msg += f"⭐️ <i>Рейтинг: {rating}/5</i>\n\n"
        game_msg += f"📝 <i>{desc}</i>\n"
        
        # Формируем Факт дня
        fact_msg = "💡 <b>ФАКТ ДНЯ</b>\n\n"
        fact_msg += f"🎮 Студия <b>{dev_name}</b> подарила миру <b>{title}</b>. "
        fact_msg += f"Игра настолько полюбилась геймерам, что ее добавили в свои библиотеки десятки тысяч человек, "
        fact_msg += f"а средний рейтинг составил <b>{rating}/5</b>!"
        
        return game_msg, fact_msg
        
    except Exception as e:
        print(f"️ Ошибка RAWG API: {e}. Используем запасной вариант.")
        return (
            "👾 <b>ИГРА ДНЯ</b>\n\n🎮 <b>Minecraft</b> <i>(2011)</i>\n\n📝 <i>Самая продаваемая игра в истории, бесконечный холст для творчества и выживания.</i>", 
            "💡 <b>ФАКТ ДНЯ</b>\n\n🎮 В Minecraft теоретическое количество возможных миров превышает число атомов в наблюдаемой Вселенной."
        )

# === РУБРИКА 2: СВЕЖИЕ НОВОСТИ (из Reddit r/games) ===
def get_gaming_news():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = "https://www.reddit.com/r/games/hot.json?limit=10"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        posts = r.json().get("data", {}).get("children", [])
        news = []
        
        for post in posts:
            title = post["data"]["title"]
            link = "https://reddit.com" + post["data"]["permalink"]
            score = post["data"]["score"]
            
            if score > 100 and
