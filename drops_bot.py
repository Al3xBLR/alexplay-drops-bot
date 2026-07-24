import requests
import os
import re
import json
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
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

# Маппинг жанров (рус -> англ) для красивых хештегов
GENRE_TAG_MAP = {
    "Экшен": "Action",
    "Action": "Action",
    "Ролевая игра": "RPG",
    "RPG": "RPG",
    "Приключение": "Adventure",
    "Стратегия": "Strategy",
    "Шутер": "Shooter",
    "Симулятор": "Simulation",
    "Головоломка": "Puzzle",
    "Платформер": "Platformer",
    "Инди": "Indie",
    "Хоррор": "Horror",
    "Гонки": "Racing",
    "Файтинг": "Fighting",
    "Казуальная": "Casual",
    "Песочница": "Sandbox",
    "Аркада": "Arcade",
    "Спорт": "Sport",
}


def send_to_telegram(chat_id, text):
    try:
        response = requests.post(TELEGRAM_URL, data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки текста: {e}")
        return False


def send_photo_to_telegram(chat_id, photo_url, caption, reply_markup=None):
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    if not photo_url:
        return send_to_telegram(chat_id, caption)

    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        if response.status_code == 200:
            print("Фото с игрой отправлено!")
            return True
        else:
            return send_to_telegram(chat_id, caption)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        return send_to_telegram(chat_id, caption)


def fmt_num(n):
    if not n:
        return "0"
    return f"{int(n):,}".replace(",", " ")


def make_hashtags(genres_list):
    tags = []
    for g in genres_list:
        clean = g.strip()
        tag = GENRE_TAG_MAP.get(clean)
        if tag and tag not in tags:
            tags.append(tag)
    tags = tags[:3]
    tags.append("ИграДня")
    tags.append("AlexPlay")
    return " ".join("#" + t for t in tags)


def build_inline_buttons(slug):
    buttons = [
        {
            "text": "🎁 Забрать халяву",
            "url": "https://t.me/AlexPlayDrops",
        }
    ]
    if slug:
        buttons.append({
            "text": "📖 Подробнее об игре",
            "url": f"https://rawg.io/games/{slug}",
        })
    return {"inline_keyboard": [buttons]}


# === ПОЛУЧЕНИЕ ДАННЫХ ИГРЫ ИЗ RAWG ===
def get_rawg_game_data():
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
            raise Exception("Пустой список игр")

        game = random.choice(games)
        slug = game.get("slug")

        detail_url = (
            f"https://api.rawg.io/api/games/{game['id']}"
            f"?key={RAWG_API_KEY}&language=ru"
        )
        detail_r = requests.get(detail_url, headers=headers, timeout=10)
        detail = detail_r.json()

        title = game.get("name", "Неизвестная игра")
        released = game.get("released")
        year = released[:4] if released else "—"
        rating = game.get("rating", "N/A")
        metacritic = detail.get("metacritic")
        playtime = detail.get("playtime")
        added = detail.get("added")
        reviews_count = detail.get("reviews_count")
        image_url = detail.get("background_image")

        developers = detail.get("developers", [])
        dev_name = developers[0]["name"] if developers else "неизвестная студия"

        publishers = detail.get("publishers", [])
        pub_name = publishers[0]["name"] if publishers else ""

        genres = detail.get("genres", [])
        genre_names = [g.get("name", "") for g in genres if g.get("name")]
        genres_str = ", ".join(genre_names[:4])

        platforms = detail.get("platforms", [])
        plat_names = []
        for p in platforms:
            pname = p.get("platform", {}).get("name", "")
            if pname:
                plat_names.append(pname)
        platforms_str = ", ".join(plat_names[:5])

        desc_raw = detail.get("description_raw", "")
        desc_clean = re.sub(r'<[^>]+>', '', desc_raw)
        if len(desc_clean) > 150:
            desc = desc_clean[:150] + "..."
        else:
            desc = desc_clean
        if not desc:
            desc = "Описание пока отсутствует в базе."

        return {
            "title": title,
            "year": year,
            "rating": rating,
            "metacritic": metacritic,
            "playtime": playtime,
            "added": added,
            "reviews_count": reviews_count,
            "dev": dev_name,
            "publisher": pub_name,
            "genres_str": genres_str,
            "genres_list": genre_names,
            "platforms_str": platforms_str,
            "desc": desc,
            "image": image_url,
            "slug": slug,
        }

    except Exception as e:
        print(f"Ошибка RAWG API: {e}. Запасной вариант.")
        return {
            "title": "Minecraft",
            "year": "2011",
            "rating": "4.4",
            "metacritic": 93,
            "playtime": 48,
            "added": 250000,
            "reviews_count": 5000,
            "dev": "Mojang Studios",
            "publisher": "Xbox Game Studios",
            "genres_str": "песочница, приключение",
            "genres_list": ["Песочница", "Приключение"],
            "platforms_str": "PC, PlayStation, Xbox, Nintendo Switch",
            "desc": "Самая продаваемая игра в истории — бесконечный холст для творчества.",
            "image": None,
            "slug": "minecraft",
        }


# === ПОДПИСЬ К ФОТО (карточка игры + паспорт + хештеги) ===
def build_game_caption(data):
    msg = "🌟 <b>ALEXPLAY HUB — ЕЖЕДНЕВНЫЙ ВЫПУСК</b>\n"
    msg += f"📅 <i>{datetime.now().strftime('%d.%m.%Y')}</i>\n\n"
    msg += "👾 <b>ИГРА ДНЯ</b>\n\n"
    msg += f"🎮 <b>{data['title']}</b> <i>({data['year']})</i>\n"
    msg += f"⭐️ Рейтинг игроков: <b>{data['rating']}/5</b>"
    if data['metacritic']:
        msg += f"  |  🏆 Metacritic: <b>{data['metacritic']}/100</b>"
    msg += "\n\n"
    msg += f"📝 <i>{data['desc']}</i>\n\n"
    msg += "📊 <b>ПАСПОРТ ИГРЫ</b>\n"
    if data['genres_str']:
        msg += f"🎭 Жанры: {data['genres_str']}\n"
    if data['platforms_str']:
        msg += f"🖥 Платформы: {data['platforms_str']}\n"
    if data['playtime'] and data['playtime'] > 0:
        msg += f"⏱ Среднее прохождение: {int(data['playtime'])} ч\n"
    if data['publisher']:
        msg += f"🏢 Издатель: {data['publisher']}\n"
    if data['added']:
        msg += f"👥 В библиотеках: {fmt_num(data['added'])}\n"
    msg += "\n" + make_hashtags(data['genres_list'])
    return msg


# === РАЗВЁРНУТЫЙ УМНЫЙ ФАКТ ДНЯ ===
def build_fact(data):
    title = data['title']
    dev = data['dev']
    publisher = data['publisher']
    metacritic = data['metacritic']
    playtime = data['playtime']
    added = data['added']
    reviews_count = data['reviews_count']
    genres_str = data['genres_str']

    parts = []

    intro = f"🎮 За созданием <b>{title}</b> стоит {dev}"
    if publisher and publisher != dev:
        intro += f", а изданием занималась <b>{publisher}</b>"
    intro += "."
    parts.append(intro)

    if metacritic:
        if metacritic >= 85:
            parts.append(
                f"Критики на Metacritic выставили ей <b>{metacritic}/100</b> "
                f"— это уровень признанных шедевров индустрии."
            )
        elif metacritic >= 75:
            parts.append(
                f"На Metacritic игра получила <b>{metacritic}/100</b> "
                f"— тёплый приём и статус крепкого релиза."
            )
        elif metacritic >= 60:
            parts.append(
                f"Оценки критиков на Metacritic (<b>{metacritic}/100</b>) "
                f"оказались сдержанными, но проект нашёл свою аудиторию."
            )
        else:
            parts.append(
                f"Metacritic оценил релиз в <b>{metacritic}/100</b> — "
                f"игра вызвала споры, и тем интереснее составить своё мнение."
            )

    if playtime and playtime > 0:
        pt = int(playtime)
        if pt >= 40:
            parts.append(
                f"Среднее прохождение занимает около <b>{pt} часов</b> — "
                f"это масштабное приключение, в которое погружаешься надолго."
            )
        elif pt >= 15:
            parts.append(
                f"В среднем игроки проводят в ней <b>{pt} часов</b> — "
                f"идеальный баланс между глубиной и длиной."
            )
        elif pt >= 5:
            parts.append(
                f"Пройти её можно примерно за <b>{pt} часов</b> — "
                f"концентрированный опыт без лишней воды."
            )
        else:
            parts.append(
                f"Это короткий, но яркий опыт — около <b>{pt} часов</b> "
                f"чистого геймплея."
            )

    if added:
        line = (
            f"На RAWG её добавили в свои библиотеки более "
            f"<b>{fmt_num(added)}</b> человек"
        )
        if reviews_count:
            line += f", оставив <b>{fmt_num(reviews_count)}</b> отзывов"
        line += " — а это знак настоящей народной любви."
        parts.append(line)

    if genres_str:
        parts.append(
            f"По духу это {genres_str.lower()} — "
            f"именно такие проекты ценят миллионы геймеров по всему миру."
        )

    return "💡 <b>ФАКТ ДНЯ</b>\n\n" + " ".join(parts)


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
            pdata = post["data"]
            title = pdata["title"]
            link = "https://reddit.com" + pdata["permalink"]
            score = pdata["score"]

            is_popular = score > 100
            is_not_weekly = not title.startswith("Weekly")

            if is_popular and is_not_weekly:
                clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                news.append({"title": clean_title, "link": link})

        return news[:3]
    except Exception as e:
        print(f"Ошибка получения новостей: {e}")
        return []


# === ПУБЛИКАЦИЯ В HUB ===
def publish_hub():
    print("Генерируем контент для @AlexPlayHub...")
    data = get_rawg_game_data()

    caption = build_game_caption(data)
    fact = build_fact(data)
    news = get_gaming_news()
    buttons = build_inline_buttons(data.get("slug"))

    # Сообщение 1: карточка с обложкой + кнопки + хештеги
    send_photo_to_telegram(HUB_CHANNEL_ID, data["image"], caption, buttons)

    # Сообщение 2: факт + новости + призыв
    text2 = fact + "\n\n━━━━━━━━━━━━━━━\n\n"

    if news:
        text2 += "📰 <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
        for i, n in enumerate(news, 1):
            text2 += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n\n"
        text2 += "━━━━━━━━━━━━━━━\n\n"

    text2 += "💬 <b>Обсуждаем в комментариях!</b>\n\n"
    text2 += "🎁 <i>Хочешь забирать игры <b>бесплатно</b>? "
    text2 += "Подпишись на нашего брата:</i>\n"
    text2 += "👉 @AlexPlayDrops\n\n"
    text2 += "🔔 <i>Включай уведомления, чтобы не пропустить!</i>"

    send_to_telegram(HUB_CHANNEL_ID, text2)
    print("Контент для @AlexPlayHub опубликован!")


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
                pdata = post["data"]
                title = pdata["title"]
                link = "https://reddit.com" + pdata["permalink"]
                pattern = r'\b(free|giveaway|100%|раздача)\b'
                if re.search(pattern, title, re.IGNORECASE):
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                    already_added = any(item['link'] == link for item in freebies)
                    if not already_added:
                        freebies.append({"title": clean_title, "link": link})
        return freebies[:6]
    except Exception as e:
        print(f"Ошибка Reddit API: {e}")
        return []


# === ПУБЛИКАЦИЯ ХАЛЯВЫ В DROPS ===
def publish_drops():
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


# === ГЛАВНАЯ ФУНКЦИЯ ===
def main():
    print("Запуск полного сканирования и генерации контента...")
    publish_hub()
    publish_drops()


if __name__ == "__main__":
    main()
