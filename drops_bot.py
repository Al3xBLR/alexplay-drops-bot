import requests
import os
import re
from datetime import datetime
import random

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")
RAWG_API_KEY = os.environ.get("RAWG_API_KEY")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID, RAWG_API_KEY]):
    print("ОШИБКА: Не найдены необходимые секреты! Проверь настройки GitHub.")
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
            print(f"Успешно отправлено в {chat_id}")
            return True
        else:
            print(f"Ошибка Telegram {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"Ошибка сети при отправке: {e}")
        return False


# === ИГРА ДНЯ + ФАКТ ДНЯ (RAWG.io на русском) ===
def get_rawg_game_and_fact():
    print("Запрашиваем игру дня из RAWG.io...")
    try:
        day_of_year = datetime.now().timetuple().tm_yday
        page = (day_of_year % 150) + 1

        url = (
            f"https://api.rawg.io/api/games?key={RAWG_API_KEY}"
            f"&language=ru&ordering=-added"
            f"&dates=1990-01-01,2025-12-31&page={page}&page_size=3"
        )
        headers = {"User-Agent": "AlexPlayBot/1.0"}

        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        games = r.json().get("results", [])

        if not games:
            raise Exception("Не удалось получить игры из RAWG")

        game = random.choice(games)

        detail_url = (
            f"https://api.rawg.io/api/games/{game['id']}"
            f"?key={RAWG_API_KEY}&language=ru"
        )
        detail_r = requests.get(detail_url, headers=headers, timeout=10)
        detail = detail_r.json()

        title = game.get("name", "Неизвестная игра")
        released = game.get("released")
        if released:
            year = released[:4]
        else:
            year = "Неизвестный год"
        rating = game.get("rating", "N/A")

        developers = detail.get("developers", [])
        if developers:
            dev_name = developers[0]["name"]
        else:
            dev_name = "Неизвестный разработчик"

        desc_raw = detail.get("description_raw", "Описание отсутствует.")
        desc_clean = re.sub(r'<[^>]+>', '', desc_raw)
        if len(desc_clean) > 250:
            desc = desc_clean[:250] + '...'
        else:
            desc = desc_clean

        game_msg = "👾 <b>ИГРА ДНЯ</b>\n\n"
        game_msg += f"🎮 <b>{title}</b> <i>({year})</i>\n"
        game_msg += f"⭐️ <i>Рейтинг: {rating}/5</i>\n\n"
        game_msg += f"📝 <i>{desc}</i>\n"

        fact_msg = "💡 <b>ФАКТ ДНЯ</b>\n\n"
        fact_msg += f"🎮 Студия <b>{dev_name}</b> подарила миру <b>{title}</b>. "
        fact_msg += "Игра настолько полюбилась геймерам, что её добавили "
        fact_msg += "в свои библиотеки десятки тысяч человек, "
        fact_msg += f"а средний рейтинг составил <b>{rating}/5</b>!"

        return game_msg, fact_msg

    except Exception as e:
        print(f"Ошибка RAWG API: {e}. Используем запасной вариант.")
        backup_game = (
            "👾 <b>ИГРА ДНЯ</b>\n\n"
            "🎮 <b>Minecraft</b> <i>(2011)</i>\n\n"
            "📝 <i>Самая продаваемая игра в истории, "
            "бесконечный холст для творчества и выживания.</i>"
        )
        backup_fact = (
            "💡 <b>ФАКТ ДНЯ</b>\n\n"
            "🎮 В Minecraft теоретическое количество возможных миров "
            "превышает число атомов в наблюдаемой Вселенной."
        )
        return backup_game, backup_fact


# === СВЕЖИЕ НОВОСТИ (Reddit r/games) ===
def get_gaming_news():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        url = "https://www.reddit.com/r/games/hot.json?limit=10"
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        posts = r.json().get("data", {}).get("children", [])
        news = []

        for post in posts:
            data = post["data"]
            title = data["title"]
            link = "https://reddit.com" + data["permalink"]
            score = data["score"]

            is_popular = score > 100
            is_not_weekly = not title.startswith("Weekly")

            if is_popular and is_not_weekly:
                clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                news.append({
                    "title": clean_title,
                    "link": link,
                    "score": score
                })

        return news[:3]
    except Exception as e:
        print(f"Ошибка получения новостей: {e}")
        return []


# === ГЛАВНЫЙ ПОСТ ДЛЯ HUB ===
def generate_hub_content():
    print("Генерируем контент для @AlexPlayHub...")

    game_post, fact_post = get_rawg_game_and_fact()
    news_list = get_gaming_news()

    final_msg = "🌟 <b>ALEXPLAY HUB — ЕЖЕДНЕВНЫЙ ВЫПУСК</b>\n\n"
    final_msg += f"📅 <i>{datetime.now().strftime('%d.%m.%Y')}</i>\n\n"
    final_msg += "━━━━━━━━━━━━━━━\n\n"

    final_msg += game_post + "\n\n"
    final_msg += "━━━━━━━━━━━━━━━\n\n"

    if news_list:
        final_msg += "📰 <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
        for i, news in enumerate(news_list, 1):
            final_msg += f"{i}. <a href='{news['link']}'>{news['title']}</a>\n\n"
        final_msg += "━━━━━━━━━━━━━━━\n\n"

    final_msg += fact_post + "\n\n"
    final_msg += "━━━━━━━━━━━━━━━\n\n"

    final_msg += "💬 <b>Обсуждаем в комментариях!</b>\n\n"
    final_msg += "🎁 <i>Хочешь забирать игры <b>бесплатно</b>? "
    final_msg += "Подпишись на нашего брата:</i>\n"
    final_msg += "👉 @AlexPlayDrops\n\n"
    final_msg += "🔔 <i>Включай уведомления, чтобы не пропустить!</i>"

    return final_msg


# === ПРОВЕРКА EPIC GAMES ===
def check_epic():
    print("Проверяем Epic Games...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        elements = []
        catalog = data.get("data", {})
        if catalog:
            search_store = catalog.get("Catalog", {}).get("searchStore", {})
            elements = search_store.get("elements", []) or []

        free_games = []
        for el in elements:
            if not isinstance(el, dict):
                continue
            price_info = el.get("price", {}).get("totalPrice", {}) or {}
            if price_info.get("discountPrice", 999999) == 0:
                free_games.append(el)
        return free_games
    except Exception as e:
        print(f"Ошибка Epic API: {e}")
        return []


# === ПРОВЕРКА ДРУГИХ ПЛОЩАДОК ===
def check_other_platforms():
    print("Проверяем Steam, GOG, Amazon, PS, Xbox...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        subreddits = ["FreeGameFindings", "FreeGamesOnSteam"]
        freebies = []

        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            posts = r.json().get("data", {}).get("children", [])
            for post in posts:
                data = post["data"]
                title = data["title"]
                link = "https://reddit.com" + data["permalink"]
                pattern = r'\b(free|giveaway|100%|раздача)\b'
                if re.search(pattern, title, re.IGNORECASE):
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                    already_added = any(item['link'] == link for item in freebies)
                    if not already_added:
                        freebies.append({
                            "title": clean_title,
                            "link": link
                        })
        return freebies[:6]
    except Exception as e:
        print(f"Ошибка Reddit API: {e}")
        return []


# === ГЛАВНАЯ ФУНКЦИЯ ===
def main():
    print("Запуск полного сканирования и генерации контента...")

    hub_content = generate_hub_content()
    send_to_telegram(HUB_CHANNEL_ID, hub_content)
    print("Контент для @AlexPlayHub опубликован!")

    epic_games = check_epic()
    other_freebies = check_other_platforms()

    if not epic_games and not other_freebies:
        drops_msg = (
            "🤖 <b>Тишина в эфире!</b>\n\n"
            "Сегодня крупных раздач не найдено. "
            "Но мы продолжаем следить 24/7! 🔔\n\n"
            "Следи за обновлениями в @AlexPlayDrops"
        )
        send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
        return

    drops_msg = "🔥 <b>ГЛОБАЛЬНЫЙ СБОР ХАЛЯВЫ!</b>\n\n"

    if epic_games:
        drops_msg += "🟣 <b>EPIC GAMES:</b>\n"
        for i, g in enumerate(epic_games[:3], 1):
            title = g.get("title", "Игра")
            price_block = g.get("price", {}).get("totalPrice", {})
            fmt = price_block.get("fmtPrice", {})
            price = fmt.get("originalPrice", "0") or "0"
            drops_msg += f"  {i}. <b>{title}</b> <i>(было {price})</i>\n"
        drops_msg += "🔗 <b>Забрать:</b> https://store.epicgames.com/ru/free-games\n\n"
    else:
        drops_msg += "🟣 <b>EPIC GAMES:</b>\n  <i>Сейчас нет активных раздач.</i>\n\n"

    if other_freebies:
        drops_msg += "🟢 <b>STEAM, GOG, AMAZON, PS, XBOX:</b>\n"
        for i, item in enumerate(other_freebies, 1):
            drops_msg += f"  {i}. <b>{item['title']}</b>\n"
            drops_msg += f"     🔗 <a href='{item['link']}'>Ссылка на раздачу</a>\n\n"
    else:
        drops_msg += "🟢 <b>STEAM, GOG, AMAZON, PS, XBOX:</b>\n"
        drops_msg += "  <i>Свежих раздач пока нет, но мы мониторим!</i>\n\n"

    drops_msg += "⏰ <i>Раздачи ограничены по времени! Забирай, пока не поздно.</i>\n\n"
    drops_msg += "🌟 <i>Больше новостей и обзоров в @AlexPlayHub</i>"

    send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
    print("Контент для @AlexPlayDrops опубликован!")


if __name__ == "__main__":
    main()
