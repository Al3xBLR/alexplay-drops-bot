import requests
import os
import re
import sys
import json
import time
import traceback
import feedparser
from datetime import datetime, timezone, timedelta

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

SCHEDULE = {9: "drops", 12: "hub_game", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}

WARNINGS = []
SOURCE_STATUS = {"epic": "—", "reddit": "—", "rawg": "—", "rss": "—", "youtube": "—", "steam": "—"}

GENRE_TAG_MAP = {
    "Экшен": "Action", "Action": "Action",
    "Ролевая игра": "RPG", "RPG": "RPG",
    "Приключение": "Adventure", "Стратегия": "Strategy",
    "Шутер": "Shooter", "Симулятор": "Simulation",
    "Головоломка": "Puzzle", "Платформер": "Platformer",
    "Инди": "Indie", "Хоррор": "Horror",
    "Гонки": "Racing", "Файтинг": "Fighting",
    "Казуальная": "Casual", "Песочница": "Sandbox",
    "Аркада": "Arcade", "Спорт": "Sport",
}

RSS_SOURCES = [
    {"name": "DTF", "url": "https://dtf.ru/rss", "lang": "ru"},
    {"name": "StopGame", "url": "https://stopgame.ru/rss/news", "lang": "ru"},
    {"name": "3DNews", "url": "https://3dnews.ru/games/rss", "lang": "ru"},
    {"name": "PC Gamer", "url": "https://www.pcgamer.com/rss/", "lang": "en"},
]

YOUTUBE_CHANNELS = [
    {"name": "Nintendo", "feed": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"},
    {"name": "PlayStation", "feed": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
    {"name": "Xbox", "feed": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
]

STEAM_SOURCES = [
    {"name": "Steam", "url": "https://store.steampowered.com/feeds/newreleases/"},
    {"name": "Steam", "url": "https://store.steampowered.com/feeds/news/"},
]


# === НАДЁЖНЫЙ ЗАПРОС С ПОВТОРАМИ (спасает от таймаутов RAWG) ===
def fetch_json(url, headers=None, timeout=20, retries=3):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_error = e
            print(f"Попытка {attempt}/{retries} не удалась: {e}")
            if attempt < retries:
                time.sleep(2)
    raise last_error


def translate_to_ru(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            parts = [seg[0] for seg in data[0] if seg and seg[0]]
            result = "".join(parts)
            if result:
                return result
    except Exception as e:
        print(f"Перевод не удался: {e}")
    return text


def send_to_telegram(chat_id, text):
    if not chat_id:
        print("Нет chat_id для отправки, пропускаю.")
        return False
    try:
        response = requests.post(TELEGRAM_URL, data={
            "chat_id": chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": False
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

    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        if response.status_code == 200:
            print("Фото с игрой отправлено!")
            return True
        else:
            WARNINGS.append(f"Фото не ушло в {chat_id}: {response.status_code}")
            return send_to_telegram(chat_id, caption)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        return send_to_telegram(chat_id, caption)


def get_chat_members(chat_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount"
        r = requests.get(url, params={"chat_id": chat_id}, timeout=10)
        if r.status_code == 200:
            return r.json().get("result", "?")
    except Exception as e:
        print(f"Ошибка счётчика подписчиков: {e}")
    return "?"


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


def build_inline_buttons(slug, trailer_url, title):
    rows = []
    rows.append([{"text": "🎁 Забрать халяву", "url": "https://t.me/AlexPlayDrops"}])
    if trailer_url:
        rows.append([{"text": "🎬 Смотреть трейлер", "url": trailer_url}])
    else:
        q = title.replace(" ", "+")
        rows.append([{
            "text": "🎬 Видеообзоры на YouTube",
            "url": f"https://www.youtube.com/results?search_query={q}+обзор+трейлер",
        }])
    if slug:
        rows.append([{"text": "📖 Подробнее об игре", "url": f"https://rawg.io/games/{slug}"}])
    return {"inline_keyboard": rows}


# === RAWG: ИГРА ДНЯ + СКРИНШОТ + ТРЕЙЛЕР (с повторами и анти-дублем) ===
def get_rawg_game_data():
    print("Запрашиваем игру дня из RAWG.io...")
    try:
        day_of_year = datetime.now().timetuple().tm_yday
        page = ((day_of_year // 3) % 150) + 1
        inner_index = day_of_year % 3

        url = (
            f"https://api.rawg.io/api/games?key={RAWG_API_KEY}"
            f"&language=ru&ordering=-added"
            f"&dates=1990-01-01,2025-12-31&page={page}&page_size=3"
        )
        headers = {"User-Agent": "AlexPlayBot/1.0"}

        games = fetch_json(url, headers).get("results", [])

        if not games:
            raise Exception("Пустой список игр")

        if inner_index >= len(games):
            inner_index = 0
        game = games[inner_index]
        slug = game.get("slug")

        detail_url = (
            f"https://api.rawg.io/api/games/{game['id']}"
            f"?key={RAWG_API_KEY}&language=ru"
        )
        detail = fetch_json(detail_url, headers)

        trailer_url = ""
        try:
            movies_url = f"https://api.rawg.io/api/games/{game['id']}/movies?key={RAWG_API_KEY}"
            movies = fetch_json(movies_url, headers).get("results", [])
            for m in movies:
                for u in (m.get("urls") or []):
                    link = u.get("url", "")
                    if "youtube.com" in link or "youtu.be" in link:
                        trailer_url = link
                        break
                if not trailer_url:
                    data_obj = m.get("data") or {}
                    vid = data_obj.get("video_id", "")
                    if vid:
                        trailer_url = f"https://www.youtube.com/watch?v={vid}"
                if not trailer_url:
                    preview = m.get("preview") or ""
                    mm = re.search(r'/vi/([^/]+)/', preview)
                    if mm:
                        trailer_url = f"https://www.youtube.com/watch?v={mm.group(1)}"
                if trailer_url:
                    break
        except Exception as e:
            print(f"Трейлер не найден: {e}")

        image_url = detail.get("background_image") or game.get("background_image")
        if not image_url:
            try:
                sh_url = f"https://api.rawg.io/api/games/{game['id']}/screenshots?key={RAWG_API_KEY}"
                shots = fetch_json(sh_url, headers).get("results", [])
                if shots:
                    image_url = shots[0].get("image")
            except Exception as e:
                print(f"Скриншоты не получены: {e}")

        title = game.get("name", "Неизвестная игра")
        released = game.get("released")
        year = released[:4] if released else "—"
        rating = game.get("rating", "N/A")
        metacritic = detail.get("metacritic")
        playtime = detail.get("playtime")
        added = detail.get("added")
        reviews_count = detail.get("reviews_count")

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

        SOURCE_STATUS["rawg"] = "✅"
        return {
            "title": title, "year": year, "rating": rating,
            "metacritic": metacritic, "playtime": playtime,
            "added": added, "reviews_count": reviews_count,
            "dev": dev_name, "publisher": pub_name,
            "genres_str": genres_str, "genres_list": genre_names,
            "platforms_str": platforms_str, "desc": desc,
            "image": image_url, "slug": slug, "trailer": trailer_url,
        }
    except Exception as e:
        print(f"Ошибка RAWG API: {e}. Запасной вариант.")
        SOURCE_STATUS["rawg"] = "⚠️"
        WARNINGS.append(f"RAWG недоступен, использован запасной пост: {e}")
        return {
            "title": "Minecraft", "year": "2011", "rating": "4.4",
            "metacritic": 93, "playtime": 48, "added": 250000,
            "reviews_count": 5000, "dev": "Mojang Studios",
            "publisher": "Xbox Game Studios",
            "genres_str": "песочница, приключение",
            "genres_list": ["Песочница", "Приключение"],
            "platforms_str": "PC, PlayStation, Xbox, Nintendo Switch",
            "desc": "Самая продаваемая игра в истории — бесконечный холст для творчества.",
            "image": None, "slug": "minecraft", "trailer": "",
        }


def build_game_caption(data):
    msg = "👾 <b>ИГРА ДНЯ</b>\n\n"
    msg += f"🎮 <b>{data['title']}</b> <i>({data['year']})</i>\n"
    msg += f"⭐️ Рейтинг игроков: <b>{data['rating']}/5</b>"
    if data['metacritic']:
        msg += f"  |  🏆 Metacritic: <b>{data['metacritic']}/100</b>"
    msg += "\n\n"
    msg += f"📝 <i>{data['desc']}</i>\n\n"

    if data.get("trailer"):
        msg += f"🎬 <a href='{data['trailer']}'><b>Смотреть трейлер</b></a>\n\n"
    else:
        q = data['title'].replace(" ", "+")
        msg += f"🎬 <a href='https://www.youtube.com/results?search_query={q}+трейлер'><b>Трейлеры и обзоры на YouTube</b></a>\n\n"

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
            parts.append(f"Критики на Metacritic выставили ей <b>{metacritic}/100</b> — это уровень признанных шедевров индустрии.")
        elif metacritic >= 75:
            parts.append(f"На Metacritic игра получила <b>{metacritic}/100</b> — тёплый приём и статус крепкого релиза.")
        elif metacritic >= 60:
            parts.append(f"Оценки критиков на Metacritic (<b>{metacritic}/100</b>) оказались сдержанными, но проект нашёл свою аудиторию.")
        else:
            parts.append(f"Metacritic оценил релиз в <b>{metacritic}/100</b> — игра вызвала споры, и тем интереснее составить своё мнение.")

    if playtime and playtime > 0:
        pt = int(playtime)
        if pt >= 40:
            parts.append(f"Среднее прохождение занимает около <b>{pt} часов</b> — это масштабное приключение.")
        elif pt >= 15:
            parts.append(f"В среднем игроки проводят в ней <b>{pt} часов</b> — идеальный баланс между глубиной и длиной.")
        elif pt >= 5:
            parts.append(f"Пройти её можно примерно за <b>{pt} часов</b> — концентрированный опыт без воды.")
        else:
            parts.append(f"Это короткий, но яркий опыт — около <b>{pt} часов</b> чистого геймплея.")

    if added:
        line = f"На RAWG её добавили в свои библиотеки более <b>{fmt_num(added)}</b> человек"
        if reviews_count:
            line += f", оставив <b>{fmt_num(reviews_count)}</b> отзывов"
        line += " — а это знак настоящей народной любви."
        parts.append(line)

    if genres_str:
        parts.append(f"По духу это {genres_str.lower()} — именно такие проекты ценят миллионы геймеров.")

    return "💡 <b>ФАКТ ДНЯ</b>\n\n" + " ".join(parts)


def get_rss_news(limit=5):
    news = []
    now = datetime.now(timezone.utc)
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published:
                    age = now - published
                    if age > timedelta(hours=24):
                        continue
                if title and link:
                    if src.get("lang") == "en":
                        title = translate_to_ru(title)
                    news.append({"title": title, "link": link, "source": src["name"], "published": published})
        except Exception as e:
            print(f"RSS {src['name']} недоступен: {e}")
            continue

    def sort_key(x):
        p = x.get("published")
        if p is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return p
    news.sort(key=sort_key, reverse=True)

    seen = set()
    unique = []
    for n in news:
        if n["link"] not in seen:
            seen.add(n["link"])
            unique.append(n)

    if unique:
        SOURCE_STATUS["rss"] = "✅"
    else:
        SOURCE_STATUS["rss"] = "⚠️"
    return unique[:limit]


def get_steam_news(limit=4):
    print("Запрашиваем новинки Steam / PC...")
    news = []
    now = datetime.now(timezone.utc)
    for src in STEAM_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published:
                    age = now - published
                    if age > timedelta(days=3):
                        continue
                if title and link:
                    news.append({"title": title, "link": link, "published": published})
        except Exception as e:
            print(f"Steam RSS недоступен: {e}")
            continue

    def sort_key(x):
        p = x.get("published")
        if p is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return p
    news.sort(key=sort_key, reverse=True)

    seen = set()
    unique = []
    for n in news:
        if n["link"] not in seen:
            seen.add(n["link"])
            unique.append(n)

    if unique:
        SOURCE_STATUS["steam"] = "✅"
    else:
        SOURCE_STATUS["steam"] = "⚠️"
    return unique[:limit]


def get_gaming_news():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        SOURCE_STATUS["reddit"] = "✅"
        return news[:3]
    except Exception as e:
        print(f"Ошибка Reddit: {e}")
        SOURCE_STATUS["reddit"] = "⚠️"
        return []


def get_youtube_videos(limit=3):
    print("Запрашиваем видео с YouTube...")
    videos = []
    for ch in YOUTUBE_CHANNELS:
        try:
            feed = feedparser.parse(ch["feed"])
            for entry in feed.entries[:2]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published:
                    age = datetime.now(timezone.utc) - published
                    if age > timedelta(days=7):
                        continue
                if title and link:
                    videos.append({"title": title, "link": link, "source": ch["name"], "published": published})
        except Exception as e:
            print(f"YouTube {ch['name']} недоступен: {e}")
            continue

    def sort_key(x):
        p = x.get("published")
        if p is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        return p
    videos.sort(key=sort_key, reverse=True)

    if videos:
        SOURCE_STATUS["youtube"] = "✅"
    else:
        SOURCE_STATUS["youtube"] = "⚠️"
    return videos[:limit]


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
        ok = send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
        if not ok:
            WARNINGS.append("Не удалось опубликовать пост в Drops.")
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
        drops_msg += "🟢 <b>STEAM, GOG, PS, XBOX, ANDROID, iOS:</b>\n"
        for i, item in enumerate(other_freebies, 1):
            drops_msg += f"  {i}. <b>{item['title']}</b>\n"
            drops_msg += f"     🔗 <a href='{item['link']}'>Ссылка на раздачу</a>\n\n"
    else:
        drops_msg += "🟢 <b>STEAM, GOG, PS, XBOX, ANDROID, iOS:</b>\n  <i>Свежих раздач пока нет, но мы мониторим!</i>\n\n"

    drops_msg += "⏰ <i>Раздачи ограничены по времени! Забирай, пока не поздно.</i>\n\n"
    drops_msg += "🌟 <i>Больше новостей и обзоров в @AlexPlayHub</i>"

    ok = send_to_telegram(DROPS_CHANNEL_ID, drops_msg)
    if not ok:
        WARNINGS.append("Не удалось опубликовать пост в Drops.")
    print("Контент для @AlexPlayDrops опубликован!")


def publish_hub_game():
    print("Публикуем Игру дня...")
    data = get_rawg_game_data()
    caption = build_game_caption(data)
    fact = build_fact(data)
    buttons = build_inline_buttons(data.get("slug"), data.get("trailer"), data.get("title"))

    ok1 = send_photo_to_telegram(HUB_CHANNEL_ID, data["image"], caption, buttons)
    if not ok1:
        WARNINGS.append("Не удалось опубликовать карточку в Hub.")
    send_to_telegram(HUB_CHANNEL_ID, fact)
    print("Игра дня опубликована!")


def publish_hub_news():
    print("Публикуем новости...")
    news = get_rss_news(limit=5)
    if not news:
        backup = get_gaming_news()
        news = [{"title": x["title"], "link": x["link"], "source": "Reddit"} for x in backup]
    if not news:
        print("Новостей нет, пропускаем.")
        return

    text = "📰 <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
    for i, n in enumerate(news, 1):
        text += f"{i}. <a href='{n['link']}'>{n['title']}</a>"
        text += f" <i>({n['source']})</i>\n\n"
    text += "\n💬 <i>Обсуждаем в комментариях!</i>"

    ok = send_to_telegram(HUB_CHANNEL_ID, text)
    if not ok:
        WARNINGS.append("Не удалось опубликовать новости в Hub.")
    print("Новости опубликованы!")


def publish_hub_steam():
    print("Публикуем новинки Steam...")
    steam = get_steam_news(limit=4)
    if not steam:
        print("Новинок Steam нет, пропускаем.")
        return

    text = "🆕 <b>НОВИНКИ STEAM / PC</b>\n\n"
    for i, n in enumerate(steam, 1):
        text += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n\n"
    text += "🌟 <i>Больше новостей в @AlexPlayHub</i>"

    ok = send_to_telegram(HUB_CHANNEL_ID, text)
    if not ok:
        WARNINGS.append("Не удалось опубликовать новинки Steam в Hub.")
    print("Новинки Steam опубликованы!")


def publish_hub_video():
    print("Публикуем трейлеры...")
    yt = get_youtube_videos(limit=3)
    if yt:
        text = "🎬 <b>ТРЕЙЛЕРЫ ОТ NINTENDO, PLAYSTATION, XBOX</b>\n\n"
        for i, v in enumerate(yt, 1):
            text += f"{i}. <a href='{v['link']}'>{v['title']}</a>"
            text += f" <i>({v['source']})</i>\n\n"
        text += "🔔 <i>Включай уведомления, чтобы не пропустить!</i>"
        ok = send_to_telegram(HUB_CHANNEL_ID, text)
        if not ok:
            WARNINGS.append("Не удалось опубликовать трейлеры в Hub.")
    else:
        print("Трейлеров нет, пропускаем.")
    print("Трейлеры обработаны!")


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
        SOURCE_STATUS["epic"] = "✅"
        return free_games
    except Exception as e:
        print(f"Ошибка Epic API: {e}")
        SOURCE_STATUS["epic"] = "⚠️"
        WARNINGS.append(f"Epic Games API недоступен: {e}")
        return []


def check_other_platforms():
    print("Проверяем другие площадки (Steam, GOG, консоли, Android, iOS)...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        subreddits = [
            "FreeGameFindings",
            "FreeGamesOnSteam",
            "AppHookup",
            "GameDealsFree",
        ]
        freebies = []
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=12"
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
                    clean_title = title.strip()
                    already_added = any(item['link'] == link for item in freebies)
                    if not already_added:
                        freebies.append({"title": clean_title, "link": link})
        return freebies[:8]
    except Exception as e:
        print(f"Ошибка Reddit (халява): {e}")
        return []


def send_alert():
    if not CHAT_ID:
        return
    text = "🚨 <b>Внимание: сбои в боте AlexPlay</b>\n\n"
    for w in WARNINGS:
        text += "⚠️ " + str(w) + "\n"
    text += "\n<i>Проверь каналы и логи во вкладке Actions на GitHub.</i>"
    if len(text) > 3500:
        text = text[:3500]
    send_to_telegram(CHAT_ID, text)


def send_pulse():
    if not CHAT_ID:
        return
    hub_count = get_chat_members(HUB_CHANNEL_ID)
    drops_count = get_chat_members(DROPS_CHANNEL_ID)

    text = "📊 <b>Дневной отчёт AlexPlay</b>\n"
    text += f"📅 <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>\n\n"
    text += f"👥 @AlexPlayHub: <b>{hub_count}</b> подписчиков\n"
    text += f"👥 @AlexPlayDrops: <b>{drops_count}</b> подписчиков\n\n"
    text += "🛰 <b>Статус источников:</b>\n"
    text += f"Epic Games: {SOURCE_STATUS['epic']}\n"
    text += f"RSS-новости: {SOURCE_STATUS['rss']}\n"
    text += f"Steam/PC: {SOURCE_STATUS['steam']}\n"
    text += f"YouTube: {SOURCE_STATUS['youtube']}\n"
    text += f"Reddit: {SOURCE_STATUS['reddit']}\n"
    text += f"RAWG: {SOURCE_STATUS['rawg']}\n\n"

    if all(v == "✅" for v in SOURCE_STATUS.values()):
        text += "✅ Всё работает штатно. Спокойной ночи! 🌙"
    else:
        text += "⚠️ Один из источников дал сбой — детали в алерте выше."
    send_to_telegram(CHAT_ID, text)


def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"КРИТИЧЕСКИЙ СБОЙ в {name}: {e}")
        print(f"Сбой в {name}: {e}")
        print(traceback.format_exc())


def main():
    print("Запуск бота AlexPlay...")

    mode = "auto"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if mode == "auto":
        moscow_hour = (datetime.now(timezone.utc).hour + 3) % 24
        mode = SCHEDULE.get(moscow_hour, "skip")
        print(f"Московское время: {moscow_hour}:00 -> режим: {mode}")

    if mode == "skip":
        print("Сейчас не время публикации. Пропускаем.")
        return

    if mode in ("drops", "all"):
        run_safe("Drops", publish_drops)
    if mode in ("hub_game", "all"):
        run_safe("HubGame", publish_hub_game)
    if mode in ("hub_news", "all"):
        run_safe("HubNews", publish_hub_news)
    if mode in ("hub_steam", "all"):
        run_safe("HubSteam", publish_hub_steam)
    if mode in ("hub_video", "all"):
        run_safe("HubVideo", publish_hub_video)

    if WARNINGS:
        send_alert()

    if mode in ("hub_video", "all"):
        send_pulse()


if __name__ == "__main__":
    main()
