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
    print("ОШИБКА: Не найдены необходимые секреты!")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SCHEDULE = {9: "drops", 12: "hub_game", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "deals": "—", "rawg": "—", "rss": "—", "youtube": "—", "steam": "—"}

# === ЗАПАСНЫЕ ИГРЫ (если RAWG недоступен) ===
FALLBACK_GAMES = [
    {"title": "The Witcher 3", "year": "2015", "dev": "CD Projekt RED", "desc": "Эпичная RPG про Геральта.", "genres": ["RPG", "Приключение"]},
    {"title": "Elden Ring", "year": "2022", "dev": "FromSoftware", "desc": "Мрачное фэнтези в открытом мире.", "genres": ["RPG", "Экшен"]},
    {"title": "Hades", "year": "2020", "dev": "Supergiant Games", "desc": "Рогалик о побеге из преисподней.", "genres": ["Экшен", "Инди"]},
    {"title": "Stardew Valley", "year": "2016", "dev": "ConcernedApe", "desc": "Уютный симулятор фермы.", "genres": ["Симулятор", "Инди"]},
    {"title": "Hollow Knight", "year": "2017", "dev": "Team Cherry", "desc": "Шедевр метроидвании.", "genres": ["Приключение", "Инди"]},
]

GENRE_TAG_MAP = {"Экшен": "Action", "Ролевая игра": "RPG", "RPG": "RPG", "Приключение": "Adventure", "Стратегия": "Strategy", "Шутер": "Shooter", "Симулятор": "Simulation", "Головоломка": "Puzzle", "Платформер": "Platformer", "Инди": "Indie", "Хоррор": "Horror", "Гонки": "Racing", "Песочница": "Sandbox"}

RSS_SOURCES = [
    {"name": "DTF", "url": "https://dtf.ru/rss", "lang": "ru"},
    {"name": "StopGame", "url": "https://stopgame.ru/rss/news", "lang": "ru"},
    {"name": "3DNews", "url": "https://3dnews.ru/games/rss", "lang": "ru"},
]

YOUTUBE_CHANNELS = [
    {"name": "Nintendo", "feed": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"},
    {"name": "PlayStation", "feed": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
    {"name": "Xbox", "feed": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
]

STEAM_SOURCES = [{"name": "Steam", "url": "https://store.steampowered.com/feeds/newreleases/"}]

def fetch_json(url, headers=None, timeout=15, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == retries:
                raise e
            time.sleep(2)

def send_to_telegram(chat_id, text):
    if not chat_id: return False
    try:
        r = requests.post(TELEGRAM_URL, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def send_photo_to_telegram(chat_id, photo_url, caption, reply_markup=None):
    if not photo_url: return send_to_telegram(chat_id, caption)
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption[:1000], "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        if r.status_code == 200: return True
        return send_to_telegram(chat_id, caption)
    except:
        return send_to_telegram(chat_id, caption)

def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except: return "?"

def fmt_num(n): return f"{int(n):,}".replace(",", " ") if n else "0"

def make_hashtags(genres_list):
    tags = [GENRE_TAG_MAP.get(g.strip()) for g in genres_list if GENRE_TAG_MAP.get(g.strip())]
    tags = list(dict.fromkeys(tags))[:3] + ["ИграДня", "AlexPlay"]
    return " ".join("#" + t for t in tags)

def build_inline_buttons(slug, trailer_url, title):
    rows = [[{"text": "🎁 Забрать халяву", "url": "https://t.me/AlexPlayDrops"}]]
    if trailer_url:
        rows.append([{"text": "🎬 Смотреть трейлер", "url": trailer_url}])
    else:
        rows.append([{"text": "🎬 Видеообзоры на YouTube", "url": f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер"}])
    if slug:
        rows.append([{"text": "📖 Подробнее об игре", "url": f"https://rawg.io/games/{slug}"}])
    return {"inline_keyboard": rows}

# === RAWG (ИГРА ДНЯ) ===
def get_rawg_game_data():
    try:
        day = datetime.now().timetuple().tm_yday
        url = f"https://api.rawg.io/api/games?key={RAWG_API_KEY}&language=ru&ordering=-added&dates=2020-01-01,2025-12-31&page={(day % 50) + 1}&page_size=3"
        games = fetch_json(url, {"User-Agent": "AlexPlayBot/1.0"}).get("results", [])
        if not games: raise Exception("Пусто")
        
        game = games[day % 3]
        detail = fetch_json(f"https://api.rawg.io/api/games/{game['id']}?key={RAWG_API_KEY}&language=ru", {"User-Agent": "AlexPlayBot/1.0"})
        
        trailer = ""
        try:
            movies = fetch_json(f"https://api.rawg.io/api/games/{game['id']}/movies?key={RAWG_API_KEY}", {"User-Agent": "AlexPlayBot/1.0"}).get("results", [])
            for m in movies:
                for u in (m.get("urls") or []):
                    if "youtube" in u.get("url", ""): trailer = u["url"]; break
                if not trailer and m.get("data", {}).get("video_id"): trailer = f"https://www.youtube.com/watch?v={m['data']['video_id']}"
                if trailer: break
        except: pass

        image = detail.get("background_image") or game.get("background_image")
        if not image:
            try:
                shots = fetch_json(f"https://api.rawg.io/api/games/{game['id']}/screenshots?key={RAWG_API_KEY}", {"User-Agent": "AlexPlayBot/1.0"}).get("results", [])
                if shots: image = shots[0].get("image")
            except: pass

        desc = re.sub(r'<[^>]+>', '', detail.get("description_raw", ""))[:150] + "..."
        genres = [g.get("name", "") for g in detail.get("genres", []) if g.get("name")]
        
        SOURCE_STATUS["rawg"] = "✅"
        return {
            "title": game.get("name", "Игра"), "year": (game.get("released") or "—")[:4],
            "rating": game.get("rating", "N/A"), "metacritic": detail.get("metacritic"),
            "playtime": detail.get("playtime"), "added": detail.get("added"),
            "dev": (detail.get("developers", [{}])[0].get("name", "Неизвестно")),
            "genres_str": ", ".join(genres[:3]), "genres_list": genres,
            "desc": desc or "Описание отсутствует.", "image": image, "slug": game.get("slug"), "trailer": trailer
        }
    except Exception as e:
        SOURCE_STATUS["rawg"] = "⚠️"
        WARNINGS.append(f"RAWG сбой: {e}")
        fb = FALLBACK_GAMES[day % len(FALLBACK_GAMES)]
        return {"title": fb["title"], "year": fb["year"], "rating": "N/A", "metacritic": None, "playtime": None, "added": None, "dev": fb["dev"], "genres_str": ", ".join(fb["genres"]), "genres_list": fb["genres"], "desc": fb["desc"], "image": None, "slug": "", "trailer": ""}

def build_game_caption(d):
    msg = f"👾 <b>ИГРА ДНЯ</b>\n🎮 <b>{d['title']}</b> <i>({d['year']})</i>\n"
    msg += f"⭐️ Рейтинг: <b>{d['rating']}/5</b>" + (f" | 🏆 Metacritic: <b>{d['metacritic']}/100</b>\n\n" if d['metacritic'] else "\n\n")
    msg += f"📝 <i>{d['desc']}</i>\n\n📊 <b>ПАСПОРТ</b>\n"
    if d['genres_str']: msg += f"🎭 Жанры: {d['genres_str']}\n"
    if d['playtime']: msg += f"⏱ Прохождение: ~{int(d['playtime'])} ч\n"
    if d['added']: msg += f"👥 В библиотеках: {fmt_num(d['added'])}\n"
    msg += "\n" + make_hashtags(d['genres_list'])
    return msg

def build_fact(d):
    parts = [f"🎮 <b>{d['title']}</b> создана студией <b>{d['dev']}</b>."]
    if d['metacritic']:
        parts.append(f"Критики оценили её на <b>{d['metacritic']}/100</b> — " + ("шедевр!" if d['metacritic']>=85 else "крепкий релиз."))
    if d['playtime'] and d['playtime'] > 0:
        parts.append(f"Среднее прохождение: <b>{int(d['playtime'])} часов</b>.")
    if d['added']:
        parts.append(f"Более <b>{fmt_num(d['added'])}</b> игроков добавили её в библиотеки.")
    return "💡 <b>ФАКТ ДНЯ</b>\n\n" + " ".join(parts)

# === НАДЁЖНЫЙ СБОР СКИДОК (ТОЛЬКО API и JSON, БЕЗ ПАРСИНГА HTML) ===
def get_all_deals():
    print("Сбор актуальных скидок...")
    deals = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. STEAM / PC (CheapShark API - 100% надёжно)
    try:
        cs_deals = fetch_json("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=15", headers, timeout=10)
        for d in cs_deals:
            savings = int(float(d.get("savings", 0)))
            if savings >= 50 and d.get("title"):
                steam_id = d.get("steamAppID", "")
                link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else "https://store.steampowered.com/"
                deals.append({"title": f"💻 [STEAM] {d['title']} (−{savings}%)", "link": link, "discount": savings})
    except Exception as e:
        print(f"CheapShark сбой: {e}")

    # 2. КОНСОЛИ и GAME PASS (Reddit JSON API - самый стабильный источник)
    queries = [
        ("xbox OR gamepass", "🟩 [XBOX/GP]"),
        ("psn OR playstation", "🟦 [PS]"),
        ("switch OR nintendo", "🟥 [SWITCH]")
    ]
    
    for query, emoji in queries:
        try:
            url = f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=15"
            data = fetch_json(url, headers, timeout=10)
            for post in data.get("data", {}).get("children", []):
                p = post["data"]
                title = p["title"]
                if "expired" in title.lower() or "ended" in title.lower():
                    continue
                
                # Извлекаем процент скидки
                discount = 0
                m = re.search(r'-\s*(\d{1,3})\s*%', title)
                if m: discount = int(m.group(1))
                elif "100%" in title.lower() or "free" in title.lower(): discount = 100
                
                if discount >= 40: # Показываем только скидки от 40%
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                    deals.append({
                        "title": f"{emoji} {clean_title}",
                        "link": "https://reddit.com" + p["permalink"],
                        "discount": discount
                    })
        except Exception as e:
            print(f"Reddit {query} сбой: {e}")

    # Сортируем по размеру скидки и убираем дубли
    deals.sort(key=lambda x: x["discount"], reverse=True)
    seen, unique = set(), []
    for d in deals:
        if d["link"] not in seen:
            seen.add(d["link"])
            unique.append(d)
            
    SOURCE_STATUS["deals"] = "✅" if unique else "⚠️"
    return unique[:10] # Топ-10 самых горячих предложений

# === ХАЛЯВА (БЕСПЛАТНО) ===
def get_freebies():
    print("Сбор бесплатных игр...")
    freebies = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Epic Games
    try:
        data = fetch_json("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers, timeout=15)
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        for el in elements:
            if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                freebies.append({"title": f"🟣 [EPIC] {el.get('title')}", "link": "https://store.epicgames.com/ru/free-games", "discount": 100})
        SOURCE_STATUS["epic"] = "✅"
    except:
        SOURCE_STATUS["epic"] = "⚠️"

    # Reddit Freebies
    try:
        data = fetch_json("https://www.reddit.com/r/FreeGameFindings/hot.json?limit=10", headers, timeout=10)
        for post in data.get("data", {}).get("children", []):
            p = post["data"]
            if re.search(r'\b(free|100%|раздача)\b', p["title"], re.IGNORECASE):
                freebies.append({"title": f"🟢 {p['title'].strip()}", "link": "https://reddit.com" + p["permalink"], "discount": 100})
    except: pass

    return freebies[:5]

# === НОВОСТИ И YOUTUBE ===
def get_rss_news():
    news, now = [], datetime.now(timezone.utc)
    for src in RSS_SOURCES:
        try:
            for entry in feedparser.parse(src["url"]).entries[:5]:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub) < timedelta(hours=24) and entry.get("title") and entry.get("link"):
                        title = entry["title"].strip()
                        if src["lang"] == "en": # Простой транслейт для PC Gamer если добавишь
                            pass 
                        news.append({"title": title, "link": entry["link"], "source": src["name"]})
        except: pass
    SOURCE_STATUS["rss"] = "✅" if news else "⚠️"
    return news[:4]

def get_youtube_videos():
    videos = []
    for ch in YOUTUBE_CHANNELS:
        try:
            for entry in feedparser.parse(ch["feed"]).entries[:1]:
                if entry.get("title") and entry.get("link"):
                    videos.append({"title": entry["title"].strip(), "link": entry["link"], "source": ch["name"]})
        except: pass
    SOURCE_STATUS["youtube"] = "✅" if videos else "⚠️"
    return videos[:3]

# === ПУБЛИКАЦИЯ ===
def publish_drops():
    freebies = get_freebies()
    deals = get_all_deals()

    # Пост 1: Халява
    if freebies:
        msg = "🔥 <b>БЕСПЛАТНЫЕ ИГРЫ ПРЯМО СЕЙЧАС!</b>\n\n"
        for i, f in enumerate(freebies, 1):
            msg += f"{i}. <b>{f['title']}</b>\n   🔗 <a href='{f['link']}'>Забрать бесплатно</a>\n\n"
        msg += "⏰ <i>Количество ограничено!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)

    # Пост 2: Скидки (только если они есть)
    if deals:
        msg = "💸 <b>ГОРЯЧИЕ СКИДКИ (от 40%)</b>\n\n"
        for i, d in enumerate(deals, 1):
            msg += f"{i}. <b>{d['title']}</b>\n   🔗 <a href='{d['link']}'>Ссылка на магазин</a>\n\n"
        msg += "⏰ <i>Цены могут измениться в любой момент!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)
    
    if not freebies and not deals:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо.</b>\nКрупных раздач и скидок сегодня не найдено, но мы продолжаем мониторить 24/7! 🔔")
    print("Drops опубликован.")

def publish_hub_game():
    d = get_rawg_game_data()
    send_photo_to_telegram(HUB_CHANNEL_ID, d["image"], build_game_caption(d), build_inline_buttons(d["slug"], d["trailer"], d["title"]))
    send_to_telegram(HUB_CHANNEL_ID, build_fact(d))
    print("Hub Game опубликован.")

def publish_hub_news():
    news = get_rss_news()
    if not news: return
    msg = "📰 <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
    for i, n in enumerate(news, 1):
        msg += f"{i}. <a href='{n['link']}'>{n['title']}</a> <i>({n['source']})</i>\n\n"
    msg += "💬 <i>Обсуждаем в комментариях!</i>"
    send_to_telegram(HUB_CHANNEL_ID, msg)
    print("Hub News опубликован.")

def publish_hub_video():
    vids = get_youtube_videos()
    if not vids: return
    msg = "🎬 <b>СВЕЖИЕ ТРЕЙЛЕРЫ</b>\n\n"
    for i, v in enumerate(vids, 1):
        msg += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
    msg += "🔔 <i>Подпишись на @AlexPlayDrops, чтобы не пропустить халяву!</i>"
    send_to_telegram(HUB_CHANNEL_ID, msg)
    print("Hub Video опубликован.")

# === ОТЧЁТЫ ===
def send_pulse():
    if not CHAT_ID: return
    msg = f"📊 <b>Отчёт AlexPlay</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f"👥 Hub: <b>{get_chat_members(HUB_CHANNEL_ID)}</b>\n"
    msg += f"👥 Drops: <b>{get_chat_members(DROPS_CHANNEL_ID)}</b>\n\n🛰 Статус:\n"
    for k, v in SOURCE_STATUS.items():
        msg += f"• {k.upper()}: {v}\n"
    msg += "\n✅ Всё работает!" if all(x=="✅" for x in SOURCE_STATUS.values()) else "\n⚠️ Есть сбои (см. алерты)."
    send_to_telegram(CHAT_ID, msg)

def send_alert():
    if not CHAT_ID or not WARNINGS: return
    msg = "🚨 <b>Сбои в боте AlexPlay:</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS)
    send_to_telegram(CHAT_ID, msg[:4000])

def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"СБОЙ {name}: {e}")
        print(traceback.format_exc())

def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    if mode == "auto":
        mode = SCHEDULE.get((datetime.now(timezone.utc).hour + 3) % 24, "skip")
    
    if mode == "skip": return
    
    if mode in ("drops", "all"): run_safe("Drops", publish_drops)
    if mode in ("hub_game", "all"): run_safe("HubGame", publish_hub_game)
    if mode in ("hub_news", "all"): run_safe("HubNews", publish_hub_news)
    if mode in ("hub_video", "all"): run_safe("HubVideo", publish_hub_video)
    
    if WARNINGS: send_alert()
    if mode in ("hub_video", "all"): send_pulse()

if __name__ == "__main__":
    main()
