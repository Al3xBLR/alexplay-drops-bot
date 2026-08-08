import requests
import os
import re
import sys
import json
import time
import traceback
import feedparser
from datetime import datetime, timezone, timedelta

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

FALLBACK_GAMES = [
    {"title": "The Witcher 3: Wild Hunt", "year": "2015", "dev": "CD Projekt RED", "desc": "Эпичная RPG про Геральта из Ривии.", "genres": ["Ролевая игра", "Приключение"]},
    {"title": "Elden Ring", "year": "2022", "dev": "FromSoftware", "desc": "Мрачное фэнтези в открытом мире.", "genres": ["Ролевая игра", "Экшен"]},
    {"title": "Baldur's Gate 3", "year": "2023", "dev": "Larian Studios", "desc": "Эталон современных CRPG.", "genres": ["Ролевая игра", "Стратегия"]},
    {"title": "Red Dead Redemption 2", "year": "2018", "dev": "Rockstar Games", "desc": "Самый живой открытый мир.", "genres": ["Экшен", "Приключение"]},
    {"title": "God of War", "year": "2018", "dev": "Santa Monica Studio", "desc": "Эпичные сражения с богами.", "genres": ["Экшен", "Приключение"]},
    {"title": "Hollow Knight", "year": "2017", "dev": "Team Cherry", "desc": "Шедевр метроидвании.", "genres": ["Приключение", "Инди"]},
    {"title": "Hades", "year": "2020", "dev": "Supergiant Games", "desc": "Рогалик о побеге из преисподней.", "genres": ["Экшен", "Инди"]},
    {"title": "Celeste", "year": "2018", "dev": "Maddy Makes Games", "desc": "Сложный и трогательный платформер.", "genres": ["Платформер", "Инди"]},
    {"title": "Stardew Valley", "year": "2016", "dev": "ConcernedApe", "desc": "Уютный симулятор фермы.", "genres": ["Симулятор", "Инди"]},
    {"title": "Portal 2", "year": "2011", "dev": "Valve", "desc": "Гениальные головоломки с порталами.", "genres": ["Головоломка", "Шутер"]},
    {"title": "Half-Life 2", "year": "2004", "dev": "Valve", "desc": "Легендарный шутер.", "genres": ["Шутер", "Приключение"]},
    {"title": "Dark Souls", "year": "2011", "dev": "FromSoftware", "desc": "Игра, давшая имя жанру.", "genres": ["Ролевая игра", "Экшен"]},
    {"title": "Mass Effect 2", "year": "2010", "dev": "BioWare", "desc": "Космическая опера.", "genres": ["Ролевая игра", "Шутер"]},
    {"title": "BioShock", "year": "2007", "dev": "Irrational Games", "desc": "Философский шутер в Восторге.", "genres": ["Шутер", "Приключение"]},
    {"title": "Disco Elysium", "year": "2019", "dev": "ZA/UM", "desc": "RPG без боёв, сражаются диалогами.", "genres": ["Ролевая игра", "Приключение"]},
    {"title": "DOOM Eternal", "year": "2020", "dev": "id Software", "desc": "Балет насилия под тяжёлый метал.", "genres": ["Шутер", "Экшен"]},
    {"title": "Cuphead", "year": "2017", "dev": "StudioMDHR", "desc": "Беги и стреляй в стиле 1930-х.", "genres": ["Экшен", "Инди"]},
    {"title": "Undertale", "year": "2015", "dev": "Toby Fox", "desc": "RPG, где можно никого не убивать.", "genres": ["Ролевая игра", "Инди"]},
    {"title": "Terraria", "year": "2011", "dev": "Re-Logic", "desc": "2D-песочница с боссами.", "genres": ["Песочница", "Приключение"]},
    {"title": "Minecraft", "year": "2011", "dev": "Mojang", "desc": "Самая продаваемая игра в истории.", "genres": ["Песочница", "Приключение"]},
    {"title": "Cyberpunk 2077", "year": "2020", "dev": "CD Projekt RED", "desc": "RPG в мегаполисе будущего.", "genres": ["Ролевая игра", "Экшен"]},
    {"title": "Sekiro: Shadows Die Twice", "year": "2019", "dev": "FromSoftware", "desc": "Отточенный бой на клинках.", "genres": ["Экшен", "Приключение"]},
    {"title": "Outer Wilds", "year": "2019", "dev": "Mobius Digital", "desc": "Космическое приключение с петлёй времени.", "genres": ["Приключение", "Головоломка"]},
    {"title": "Slay the Spire", "year": "2019", "dev": "MegaCrit", "desc": "Карточный рогалик.", "genres": ["Стратегия", "Инди"]},
]

GENRE_TAG_MAP = {
    "Экшен": "Action", "Action": "Action", "Ролевая игра": "RPG", "RPG": "RPG",
    "Приключение": "Adventure", "Стратегия": "Strategy", "Шутер": "Shooter",
    "Симулятор": "Simulation", "Головоломка": "Puzzle", "Платформер": "Platformer",
    "Инди": "Indie", "Хоррор": "Horror", "Гонки": "Racing", "Файтинг": "Fighting",
    "Казуальная": "Casual", "Песочница": "Sandbox", "Аркада": "Arcade", "Спорт": "Sport",
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


def fetch_json(url, headers=None, timeout=25, retries=4):
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
            return True
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
        print(f"Ошибка счётчика: {e}")
    return "?"


def fmt_num(n):
    if not n:
        return "0"
    return f"{int(n):,}".replace(",", " ")


def make_hashtags(genres_list):
    tags = []
    for g in genres_list:
        tag = GENRE_TAG_MAP.get(g.strip())
        if tag and tag not in tags:
            tags.append(tag)
    tags = tags[:3]
    tags += ["ИграДня", "AlexPlay"]
    return " ".join("#" + t for t in tags)


def build_inline_buttons(slug, trailer_url, title):
    rows = [[{"text": "🎁 Забрать халяву", "url": "https://t.me/AlexPlayDrops"}]]
    if trailer_url:
        rows.append([{"text": "🎬 Смотреть трейлер", "url": trailer_url}])
    else:
        q = title.replace(" ", "+")
        rows.append([{"text": "🎬 Видеообзоры на YouTube",
                      "url": f"https://www.youtube.com/results?search_query={q}+обзор+трейлер"}])
    if slug:
        rows.append([{"text": "📖 Подробнее об игре", "url": f"https://rawg.io/games/{slug}"}])
    return {"inline_keyboard": rows}


def get_fallback_game():
    idx = datetime.now().timetuple().tm_yday % len(FALLBACK_GAMES)
    fb = FALLBACK_GAMES[idx]
    return {
        "title": fb["title"], "year": fb["year"], "rating": "N/A",
        "metacritic": None, "playtime": None, "added": None, "reviews_count": None,
        "dev": fb["dev"], "publisher": "",
        "genres_str": ", ".join(fb["genres"]), "genres_list": fb["genres"],
        "platforms_str": "PC", "desc": fb["desc"], "image": None, "slug": "", "trailer": "",
    }


def get_rawg_game_data():
    print("Запрашиваем игру дня из RAWG.io...")
    try:
        day_of_year = datetime.now().timetuple().tm_yday
        page = ((day_of_year // 3) % 150) + 1
        inner_index = day_of_year % 3
        url = (f"https://api.rawg.io/api/games?key={RAWG_API_KEY}"
               f"&language=ru&ordering=-added"
               f"&dates=1990-01-01,2025-12-31&page={page}&page_size=3")
        headers = {"User-Agent": "AlexPlayBot/1.0"}
        games = fetch_json(url, headers).get("results", [])
        if not games:
            raise Exception("Пустой список игр")
        if inner_index >= len(games):
            inner_index = 0
        game = games[inner_index]
        slug = game.get("slug")
        detail = fetch_json(f"https://api.rawg.io/api/games/{game['id']}?key={RAWG_API_KEY}&language=ru", headers)

        trailer_url = ""
        try:
            movies = fetch_json(f"https://api.rawg.io/api/games/{game['id']}/movies?key={RAWG_API_KEY}", headers).get("results", [])
            for m in movies:
                for u in (m.get("urls") or []):
                    link = u.get("url", "")
                    if "youtube.com" in link or "youtu.be" in link:
                        trailer_url = link
                        break
                if not trailer_url:
                    vid = (m.get("data") or {}).get("video_id", "")
                    if vid:
                        trailer_url = f"https://www.youtube.com/watch?v={vid}"
                if not trailer_url:
                    mm = re.search(r'/vi/([^/]+)/', m.get("preview") or "")
                    if mm:
                        trailer_url = f"https://www.youtube.com/watch?v={mm.group(1)}"
                if trailer_url:
                    break
        except Exception as e:
            print(f"Трейлер не найден: {e}")

        image_url = detail.get("background_image") or game.get("background_image")
        if not image_url:
            try:
                shots = fetch_json(f"https://api.rawg.io/api/games/{game['id']}/screenshots?key={RAWG_API_KEY}", headers).get("results", [])
                if shots:
                    image_url = shots[0].get("image")
            except Exception as e:
                print(f"Скриншоты не получены: {e}")

        title = game.get("name", "Неизвестная игра")
        released = game.get("released")
        year = released[:4] if released else "—"
        developers = detail.get("developers", [])
        dev_name = developers[0]["name"] if developers else "неизвестная студия"
        publishers = detail.get("publishers", [])
        pub_name = publishers[0]["name"] if publishers else ""
        genres = detail.get("genres", [])
        genre_names = [g.get("name", "") for g in genres if g.get("name")]
        platforms = detail.get("platforms", [])
        plat_names = [p.get("platform", {}).get("name", "") for p in platforms if p.get("platform", {}).get("name")]

        desc_raw = detail.get("description_raw", "")
        desc_clean = re.sub(r'<[^>]+>', '', desc_raw)
        desc = (desc_clean[:150] + "...") if len(desc_clean) > 150 else desc_clean
        if not desc:
            desc = "Описание пока отсутствует в базе."

        SOURCE_STATUS["rawg"] = "✅"
        return {
            "title": title, "year": year, "rating": game.get("rating", "N/A"),
            "metacritic": detail.get("metacritic"), "playtime": detail.get("playtime"),
            "added": detail.get("added"), "reviews_count": detail.get("reviews_count"),
            "dev": dev_name, "publisher": pub_name,
            "genres_str": ", ".join(genre_names[:4]), "genres_list": genre_names,
            "platforms_str": ", ".join(plat_names[:5]), "desc": desc,
            "image": image_url, "slug": slug, "trailer": trailer_url,
        }
    except Exception as e:
        print(f"Ошибка RAWG API: {e}. Берём запасную игру дня.")
        SOURCE_STATUS["rawg"] = "⚠️"
        WARNINGS.append(f"RAWG недоступен, использована запасная игра дня: {e}")
        return get_fallback_game()


def build_game_caption(data):
    msg = "👾 <b>ИГРА ДНЯ</b>\n\n"
    msg += f"🎮 <b>{data['title']}</b> <i>({data['year']})</i>\n"
    msg += f"⭐️ Рейтинг игроков: <b>{data['rating']}/5</b>"
    if data['metacritic']:
        msg += f"  |  🏆 Metacritic: <b>{data['metacritic']}/100</b>"
    msg += "\n\n" + f"📝 <i>{data['desc']}</i>\n\n"
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
    title, dev = data['title'], data['dev']
    publisher, metacritic = data['publisher'], data['metacritic']
    playtime, added = data['playtime'], data['added']
    reviews_count, genres_str = data['reviews_count'], data['genres_str']
    parts = []
    intro = f"🎮 За созданием <b>{title}</b> стоит {dev}"
    if publisher and publisher != dev:
        intro += f", а изданием занималась <b>{publisher}</b>"
    parts.append(intro + ".")
    if metacritic:
        if metacritic >= 85:
            parts.append(f"Критики на Metacritic выставили ей <b>{metacritic}/100</b> — уровень признанных шедевров.")
        elif metacritic >= 75:
            parts.append(f"На Metacritic игра получила <b>{metacritic}/100</b> — тёплый приём и статус крепкого релиза.")
        elif metacritic >= 60:
            parts.append(f"Оценки критиков на Metacritic (<b>{metacritic}/100</b>) сдержанные, но проект нашёл свою аудиторию.")
        else:
            parts.append(f"Metacritic оценил релиз в <b>{metacritic}/100</b> — игра вызвала споры.")
    if playtime and playtime > 0:
        pt = int(playtime)
        if pt >= 40:
            parts.append(f"Среднее прохождение — около <b>{pt} часов</b>: масштабное приключение.")
        elif pt >= 15:
            parts.append(f"В среднем игроки проводят в ней <b>{pt} часов</b> — идеальный баланс.")
        elif pt >= 5:
            parts.append(f"Пройти можно примерно за <b>{pt} часов</b> — концентрированный опыт.")
        else:
            parts.append(f"Это короткий, но яркий опыт — около <b>{pt} часов</b>.")
    if added:
        line = f"На RAWG её добавили в библиотеки более <b>{fmt_num(added)}</b> человек"
        if reviews_count:
            line += f", оставив <b>{fmt_num(reviews_count)}</b> отзывов"
        parts.append(line + " — знак настоящей народной любви.")
    if genres_str:
        parts.append(f"По духу это {genres_str.lower()} — именно такие проекты ценят миллионы геймеров.")
    return "💡 <b>ФАКТ ДНЯ</b>\n\n" + " ".join(parts)


def get_rss_news(limit=5):
    news, now = [], datetime.now(timezone.utc)
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published and (now - published) > timedelta(hours=24):
                    continue
                if title and link:
                    if src.get("lang") == "en":
                        title = translate_to_ru(title)
                    news.append({"title": title, "link": link, "source": src["name"], "published": published})
        except Exception as e:
            print(f"RSS {src['name']} недоступен: {e}")
    news.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    seen, unique = set(), []
    for n in news:
        if n["link"] not in seen:
            seen.add(n["link"]); unique.append(n)
    SOURCE_STATUS["rss"] = "✅" if unique else "⚠️"
    return unique[:limit]


def get_steam_news(limit=4):
    news, now = [], datetime.now(timezone.utc)
    for src in STEAM_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:8]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published and (now - published) > timedelta(days=3):
                    continue
                if title and link:
                    news.append({"title": title, "link": link, "published": published})
        except Exception as e:
            print(f"Steam RSS недоступен: {e}")
    news.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    seen, unique = set(), []
    for n in news:
        if n["link"] not in seen:
            seen.add(n["link"]); unique.append(n)
    SOURCE_STATUS["steam"] = "✅" if unique else "⚠️"
    return unique[:limit]


def get_gaming_news():
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://www.reddit.com/r/games/hot.json?limit=10", headers=headers, timeout=10)
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        news = []
        for post in posts:
            p = post["data"]
            if p["score"] > 100 and not p["title"].startswith("Weekly"):
                clean = re.sub(r'^\[[^\]]*\]\s*', '', p["title"])
                news.append({"title": clean, "link": "https://reddit.com" + p["permalink"]})
        SOURCE_STATUS["reddit"] = "✅"
        return news[:3]
    except Exception as e:
        print(f"Ошибка Reddit: {e}")
        SOURCE_STATUS["reddit"] = "⚠️"
        return []


def get_youtube_videos(limit=3):
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
                if published and (datetime.now(timezone.utc) - published) > timedelta(days=7):
                    continue
                if title and link:
                    videos.append({"title": title, "link": link, "source": ch["name"], "published": published})
        except Exception as e:
            print(f"YouTube {ch['name']} недоступен: {e}")
    videos.sort(key=lambda x: x.get("published") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    SOURCE_STATUS["youtube"] = "✅" if videos else "⚠️"
    return videos[:limit]


def check_other_platforms():
    print("Проверяем халяву...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        subreddits = ["FreeGameFindings", "FreeGamesOnSteam", "AppHookup", "GameDealsFree"]
        freebies = []
        for sub in subreddits:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=12", headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            for post in r.json().get("data", {}).get("children", []):
                p = post["data"]
                if re.search(r'\b(free|giveaway|100%|раздача)\b', p["title"], re.IGNORECASE):
                    link = "https://reddit.com" + p["permalink"]
                    if not any(i['link'] == link for i in freebies):
                        freebies.append({"title": p["title"].strip(), "link": link})
        return freebies[:5]
    except Exception as e:
        print(f"Ошибка Reddit (халява): {e}")
        return []


# === ИЗВЛЕЧЕНИЕ РАЗМЕРА СКИДКИ ИЗ ТЕКСТА ===
def extract_discount(text):
    m = re.search(r'-\s*(\d{1,3})\s*%', text)
    if m:
        return int(m.group(1))
    low = text.lower()
    if "100%" in low or "free" in low:
        return 100
    return 0


# === СКИДКИ КОНСОЛЕЙ ЧЕРЕЗ ПОИСК r/GameDeals (надёжно) ===
def check_reddit_platform_deals(query, emoji, platform, limit=5):
    print(f"Ищу {platform}-скидки в Reddit (запрос: {query})...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = (f"https://www.reddit.com/r/GameDeals/search.json"
               f"?q={query}&restrict_sr=1&sort=new&t=week&limit=30")
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"Reddit-поиск вернул {r.status_code}")
            return []
        posts = r.json().get("data", {}).get("children", [])
        deals = []
        for post in posts:
            p = post["data"]
            title, low = p["title"], p["title"].lower()
            link = "https://reddit.com" + p["permalink"]
            if "expired" in low or "ended" in low:
                continue
            discount = extract_discount(title)
            if discount < 30:
                continue
            clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
            deals.append({"title": f"{emoji} [{platform}] {clean_title}", "link": link, "discount": discount})
        seen, unique = set(), []
        for d in deals:
            if d["link"] not in seen:
                seen.add(d["link"]); unique.append(d)
        unique.sort(key=lambda x: x["discount"], reverse=True)
        return unique[:limit]
    except Exception as e:
        print(f"Ошибка Reddit-поиска {query}: {e}")
        return []


# === СКИДКИ STEAM ЧЕРЕЗ БЕСПЛАТНЫЙ API CheapShark ===
def check_steam_cheapshark():
    print("Проверяю скидки Steam через CheapShark...")
    try:
        url = "https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=20"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        deals = []
        for d in r.json():
            title = d.get("title", "")
            savings = int(float(d.get("savings", 0)))
            steam_id = d.get("steamAppID", "")
            link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else "https://store.steampowered.com/"
            if title and savings >= 50:
                deals.append({"title": f"💻 [STEAM] {title} (−{savings}%)", "link": link, "discount": savings})
        deals.sort(key=lambda x: x["discount"], reverse=True)
        return deals[:5]
    except Exception as e:
        print(f"Ошибка CheapShark: {e}")
        return []


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
            elements = catalog.get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
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


def publish_drops():
    epic_games = check_epic()
    other_freebies = check_other_platforms()

    # Скидки по всем платформам из надёжных источников
    all_deals = []
    all_deals += check_reddit_platform_deals("xbox", "🟩", "XBOX")
    all_deals += check_reddit_platform_deals("psn", "🟦", "PLAYSTATION")
    all_deals += check_reddit_platform_deals("switch", "🟥", "SWITCH")
    all_deals += check_steam_cheapshark()

    seen, merged_deals = set(), []
    for d in all_deals:
        if d["link"] not in seen:
            seen.add(d["link"]); merged_deals.append(d)
    merged_deals.sort(key=lambda x: x.get("discount", 0), reverse=True)
    merged_deals = merged_deals[:12]

    has_freebies = bool(epic_games) or bool(other_freebies)

    if has_freebies:
        drops_msg = "🔥 <b>ГЛОБАЛЬНЫЙ СБОР ХАЛЯВЫ!</b>\n\n"
        if epic_games:
            drops_msg += "🟣 <b>EPIC GAMES:</b>\n"
            for i, g in enumerate(epic_games[:3], 1):
                title = g.get("title", "Игра")
                price = g.get("price", {}).get("totalPrice", {}).get("fmtPrice", {}).get("originalPrice", "0") or "0"
                drops_msg += f"  {i}. <b>{title}</b> <i>(было {price})</i>\n"
            drops_msg += "🔗 <b>Забрать:</b> https://store.epicgames.com/ru/free-games\n\n"
        else:
            drops_msg += "🟣 <b>EPIC GAMES:</b>\n  <i>Сейчас нет активных раздач.</i>\n\n"
        if other_freebies:
            drops_msg += "🟢 <b>STEAM, GOG, PS, XBOX, ANDROID, iOS:</b>\n"
            for i, item in enumerate(other_freebies, 1):
                drops_msg += f"  {i}. <b>{item['title']}</b>\n     🔗 <a href='{item['link']}'>Ссылка</a>\n\n"
        drops_msg += "⏰ <i>Раздачи ограничены по времени!</i>\n🌟 <i>Больше новостей в @AlexPlayHub</i>"
        if not send_to_telegram(DROPS_CHANNEL_ID, drops_msg):
            WARNINGS.append("Не удалось опубликовать халяву в Drops.")

    if merged_deals:
        disc_msg = "💸 <b>ГОРЯЧИЕ СКИДКИ — XBOX, PLAYSTATION, SWITCH, STEAM!</b>\n\n"
        for i, d in enumerate(merged_deals, 1):
            disc_msg += f"  {i}. <b>{d['title']}</b>\n     🔗 <a href='{d['link']}'>Ссылка на скидку</a>\n\n"
        disc_msg += "⏰ <i>Скидки ограничены по времени!</i>\n🎁 <i>Бесплатные игры — в этом же канале 😉</i>"
        if not send_to_telegram(DROPS_CHANNEL_ID, disc_msg):
            WARNINGS.append("Не удалось опубликовать скидки в Drops.")

    if not has_freebies and not merged_deals:
        send_to_telegram(DROPS_CHANNEL_ID,
            "🤖 <b>Тишина в эфире!</b>\n\nСегодня раздач и крупных скидок не найдено. Мы следим 24/7! 🔔")
    print("Контент для @AlexPlayDrops опубликован!")


def publish_hub_game():
    data = get_rawg_game_data()
    caption = build_game_caption(data)
    fact = build_fact(data)
    buttons = build_inline_buttons(data.get("slug"), data.get("trailer"), data.get("title"))
    if not send_photo_to_telegram(HUB_CHANNEL_ID, data["image"], caption, buttons):
        WARNINGS.append("Не удалось опубликовать карточку в Hub.")
    send_to_telegram(HUB_CHANNEL_ID, fact)
    print("Игра дня опубликована!")


def publish_hub_news():
    news = get_rss_news(limit=5)
    if not news:
        news = [{"title": x["title"], "link": x["link"], "source": "Reddit"} for x in get_gaming_news()]
    if not news:
        return
    text = "📰 <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
    for i, n in enumerate(news, 1):
        text += f"{i}. <a href='{n['link']}'>{n['title']}</a> <i>({n['source']})</i>\n\n"
    text += "\n💬 <i>Обсуждаем в комментариях!</i>"
    if not send_to_telegram(HUB_CHANNEL_ID, text):
        WARNINGS.append("Не удалось опубликовать новости в Hub.")
    print("Новости опубликованы!")


def publish_hub_steam():
    steam = get_steam_news(limit=4)
    if not steam:
        return
    text = "🆕 <b>НОВИНКИ STEAM / PC</b>\n\n"
    for i, n in enumerate(steam, 1):
        text += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n\n"
    text += "🌟 <i>Больше новостей в @AlexPlayHub</i>"
    if not send_to_telegram(HUB_CHANNEL_ID, text):
        WARNINGS.append("Не удалось опубликовать новинки Steam в Hub.")
    print("Новинки Steam опубликованы!")


def publish_hub_video():
    yt = get_youtube_videos(limit=3)
    if not yt:
        return
    text = "🎬 <b>ТРЕЙЛЕРЫ ОТ NINTENDO, PLAYSTATION, XBOX</b>\n\n"
    for i, v in enumerate(yt, 1):
        text += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
    text += "🔔 <i>Включай уведомления, чтобы не пропустить!</i>"
    if not send_to_telegram(HUB_CHANNEL_ID, text):
        WARNINGS.append("Не удалось опубликовать трейлеры в Hub.")
    print("Трейлеры опубликованы!")


def send_alert():
    if not CHAT_ID:
        return
    text = "🚨 <b>Внимание: сбои в боте AlexPlay</b>\n\n"
    for w in WARNINGS:
        text += "⚠️ " + str(w) + "\n"
    text += "\n<i>Проверь каналы и логи во вкладке Actions на GitHub.</i>"
    send_to_telegram(CHAT_ID, text[:3500])


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
    for k, label in [("epic", "Epic Games"), ("rss", "RSS-новости"), ("steam", "Steam/PC"),
                     ("youtube", "YouTube"), ("reddit", "Reddit"), ("rawg", "RAWG")]:
        text += f"{label}: {SOURCE_STATUS[k]}\n"
    text += "\n✅ Всё работает штатно. Спокойной ночи! 🌙" if all(v == "✅" for v in SOURCE_STATUS.values()) else "\n⚠️ Один из источников дал сбой — детали в алерте выше."
    send_to_telegram(CHAT_ID, text)


def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"КРИТИЧЕСКИЙ СБОЙ в {name}: {e}")
        print(f"Сбой в {name}: {e}")
        print(traceback.format_exc())


def main():
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
