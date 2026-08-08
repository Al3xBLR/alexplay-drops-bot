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

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("ОШИБКА: Не найдены необходимые секреты! Проверь настройки GitHub.")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SCHEDULE = {9: "drops", 12: "hub_game", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "gamerpower": "—", "cheapshark": "—", "reddit": "—", "rss": "—", "youtube": "—"}

# === ЛОКАЛЬНАЯ БАЗА ИГР (замена RAWG) ===
# 60+ культовых игр с описаниями и фактами
GAMES_DB = [
    {"title": "The Witcher 3: Wild Hunt", "year": "2015", "dev": "CD Projekt RED", "desc": "Эпичная RPG про Геральта из Ривии с одним из лучших сюжетов в истории игр.", "fact": "Игра получила более 800 наград, включая 'Игра года' от множества изданий. Её разработка стоила около $81 млн.", "genres": ["RPG", "Приключение"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Elden Ring", "year": "2022", "dev": "FromSoftware", "desc": "Мрачное фэнтези в открытом мире от создателей Dark Souls и Джорджа Мартина.", "fact": "Мир игры создавался совместно с Джорджем Мартином, который написал предысторию и мифологию.", "genres": ["RPG", "Экшен"], "platforms": "PC, PS, Xbox"},
    {"title": "Baldur's Gate 3", "year": "2023", "dev": "Larian Studios", "desc": "Эталон современных CRPG с невероятной свободой выбора и тактическими боями.", "fact": "Разработка заняла более 6 лет. Игра получила рекордное количество наград 'Игра года'.", "genres": ["RPG", "Стратегия"], "platforms": "PC, PS, Xbox"},
    {"title": "Red Dead Redemption 2", "year": "2018", "dev": "Rockstar Games", "desc": "Самый живой открытый мир и история о закате эпохи Дикого Запада.", "fact": "В игре более 500 000 строк диалогов. Сценарий насчитывает более 2000 страниц.", "genres": ["Экшен", "Приключение"], "platforms": "PC, PS, Xbox"},
    {"title": "Cyberpunk 2077", "year": "2020", "dev": "CD Projekt RED", "desc": "Иммерсивная RPG в мегаполисе будущего с Киану Ривзом в главной роли.", "fact": "После выхода игра получила более 20 крупных обновлений, которые полностью её преобразили.", "genres": ["RPG", "Экшен"], "platforms": "PC, PS, Xbox"},
    {"title": "Grand Theft Auto V", "year": "2013", "dev": "Rockstar North", "desc": "Феномен поп-культуры. Сатира на американскую мечту и бесконечные возможности.", "fact": "Самая прибыльная развлекательная продукция в истории — заработала более $8 млрд.", "genres": ["Экшен", "Приключение"], "platforms": "PC, PS, Xbox"},
    {"title": "The Legend of Zelda: Breath of the Wild", "year": "2017", "dev": "Nintendo", "desc": "Революция в дизайне открытых миров. Полная свобода исследования.", "fact": "Физический движок игры настолько продвинут, что игроки находят новые способы прохождения спустя годы.", "genres": ["Приключение", "Экшен"], "platforms": "Switch, Wii U"},
    {"title": "God of War", "year": "2018", "dev": "Santa Monica Studio", "desc": "Эпичные сражения с богами скандинавской мифологии и история отца и сына.", "fact": "Вся игра снята одним непрерывным планом без склеек камеры.", "genres": ["Экшен", "Приключение"], "platforms": "PC, PS"},
    {"title": "Dark Souls", "year": "2011", "dev": "FromSoftware", "desc": "Игра, давшая имя целому жанру. Мрачный мир и принцип 'prepare to die'.", "fact": "Сложность игры стала культурным феноменом и породила десятки подражателей.", "genres": ["RPG", "Экшен"], "platforms": "PC, PS, Xbox"},
    {"title": "Portal 2", "year": "2011", "dev": "Valve", "desc": "Гениальные головоломки с порталами, блестящий юмор и лучший злодей — GLaDOS.", "fact": "Кооперативный режим был добавлен после того, как разработчики увидели, как игроки проходят уровни вместе.", "genres": ["Головоломка", "Шутер"], "platforms": "PC, PS, Xbox"},
    {"title": "Half-Life 2", "year": "2004", "dev": "Valve", "desc": "Легендарный шутер, навсегда изменивший индустрию физикой и повествованием.", "fact": "Игра не использует кат-сцены — всё повествование происходит в реальном времени.", "genres": ["Шутер", "Приключение"], "platforms": "PC, Xbox"},
    {"title": "Mass Effect 2", "year": "2010", "dev": "BioWare", "desc": "Космическая опера, где твои решения действительно имеют значение.", "fact": "Финальная миссия 'Suicide Mission' меняется в зависимости от того, насколько хорошо ты подготовился.", "genres": ["RPG", "Шутер"], "platforms": "PC, PS, Xbox"},
    {"title": "BioShock", "year": "2007", "dev": "Irrational Games", "desc": "Философский шутер в подводном городе-утопии Восторг.", "fact": "Сюжетный твист в середине игры считается одним из лучших в истории видеоигр.", "genres": ["Шутер", "Приключение"], "platforms": "PC, PS, Xbox"},
    {"title": "Disco Elysium", "year": "2019", "dev": "ZA/UM", "desc": "Революционная RPG без боёв, где сражаются с помощью диалогов и мыслей.", "fact": "Игра основана на настольной RPG, которую создатели разрабатывали более 10 лет.", "genres": ["RPG", "Приключение"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Hades", "year": "2020", "dev": "Supergiant Games", "desc": "Рогалик о сыне Аида, пытающемся сбежать из преисподней.", "fact": "Первая игра в жанре roguelike, получившая премию Хьюго за лучший сюжет.", "genres": ["Экшен", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Hollow Knight", "year": "2017", "dev": "Team Cherry", "desc": "Шедевр метроидвании в красивом рисованном стиле с огромным миром.", "fact": "Игра создана всего тремя разработчиками и собрала более $57 млн на Kickstarter.", "genres": ["Приключение", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Celeste", "year": "2018", "dev": "Maddy Makes Games", "desc": "Сложный и трогательный платформер о преодолении тревоги и панических атак.", "fact": "Игра включает режим помощи для людей с ограниченными возможностями.", "genres": ["Платформер", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Stardew Valley", "year": "2016", "dev": "ConcernedApe", "desc": "Уютный симулятор фермы, созданный одним человеком за 4 года.", "fact": "Один разработчик создал всю игру: код, графику, музыку и сюжет.", "genres": ["Симулятор", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Undertale", "year": "2015", "dev": "Toby Fox", "desc": "RPG, где тебе не обязательно кого-то убивать. Ломает четвёртую стену.", "fact": "Игра стала культурным феноменом и породила огромное количество фанатского контента.", "genres": ["RPG", "Инди"], "platforms": "PC, PS, Switch"},
    {"title": "Terraria", "year": "2011", "dev": "Re-Logic", "desc": "2D-песочница с огромной глубиной, боссами и бесконечным исследованием.", "fact": "Игра получает бесплатные обновления уже более 10 лет после релиза.", "genres": ["Песочница", "Приключение"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Minecraft", "year": "2011", "dev": "Mojang", "desc": "Самая продаваемая игра в истории — бесконечный холст для творчества.", "fact": "Продано более 238 млн копий — больше, чем у любой другой игры в истории.", "genres": ["Песочница", "Приключение"], "platforms": "Все платформы"},
    {"title": "Doom Eternal", "year": "2020", "dev": "id Software", "desc": "Балет насилия под тяжёлый метал. Быстрее, злее, яростнее.", "fact": "Игра требует от игрока постоянного движения и агрессивного стиля игры.", "genres": ["Шутер", "Экшен"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Sekiro: Shadows Die Twice", "year": "2019", "dev": "FromSoftware", "desc": "Отточенный бой на клинках в Японии эпохи сэгоку.", "fact": "Боевая система построена на ритме парирований и считается одной из лучших в индустрии.", "genres": ["Экшен", "Приключение"], "platforms": "PC, PS, Xbox"},
    {"title": "Outer Wilds", "year": "2019", "dev": "Mobius Digital", "desc": "Космическое приключение с петлёй времени. Шедевр геймдизайна.", "fact": "Единственный прогресс в игре — знания игрока. Нет уровней, экипировки или улучшений.", "genres": ["Приключение", "Головоломка"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Slay the Spire", "year": "2019", "dev": "MegaCrit", "desc": "Карточный рогалик, установивший стандарт жанра.", "fact": "Игра стала настолько популярной, что породила десятки подражателей в жанре deckbuilder.", "genres": ["Стратегия", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Dead Cells", "year": "2018", "dev": "Motion Twin", "desc": "Динамичный 'roguevania' с потрясающей боевой системой.", "fact": "Разработчики выпустили более 20 бесплатных обновлений после релиза.", "genres": ["Экшен", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Cuphead", "year": "2017", "dev": "StudioMDHR", "desc": "Беги и стреляй в стиле мультфильмов 1930-х. Вся анимация рисовалась вручную.", "fact": "Разработка заняла 7 лет. Вся анимация создана на бумаге и оцифрована.", "genres": ["Экшен", "Инди"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Resident Evil 4", "year": "2005", "dev": "Capcom", "desc": "Революционный шутер, изменивший жанр хоррор-экшенов навсегда.", "fact": "Игра была переделана 4 раза в процессе разработки, прежде чем вышла финальная версия.", "genres": ["Хоррор", "Экшен"], "platforms": "PC, PS, Xbox, Switch"},
    {"title": "Bloodborne", "year": "2015", "dev": "FromSoftware", "desc": "Готический хоррор с быстрым агрессивным геймплеем и лавкрафтовскими ужасами.", "fact": "Игра была эксклюзивом PS4 и до сих пор не вышла на других платформах.", "genres": ["RPG", "Экшен"], "platforms": "PS"},
    {"title": "Persona 5 Royal", "year": "2019", "dev": "Atlus", "desc": "Стильная JRPG о старшеклассниках-призраках с потрясающим саундтреком.", "fact": "Игра содержит более 100 часов контента и одну из самых стильных UI-систем в истории.", "genres": ["RPG", "Приключение"], "platforms": "PC, PS, Xbox, Switch"},
]

GENRE_TAG_MAP = {"Экшен": "Action", "RPG": "RPG", "Приключение": "Adventure", "Стратегия": "Strategy", "Шутер": "Shooter", "Симулятор": "Simulation", "Головоломка": "Puzzle", "Платформер": "Platformer", "Инди": "Indie", "Хоррор": "Horror", "Гонки": "Racing", "Песочница": "Sandbox"}

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


# === ИГРА ДНЯ (локальная база) ===
def get_game_of_day():
    day = datetime.now().timetuple().tm_yday
    game = GAMES_DB[day % len(GAMES_DB)]
    return {
        "title": game["title"], "year": game["year"], "dev": game["dev"],
        "desc": game["desc"], "fact": game["fact"],
        "genres_str": ", ".join(game["genres"]), "genres_list": game["genres"],
        "platforms": game["platforms"]
    }


def build_game_caption(d):
    msg = f"👾 <b>ИГРА ДНЯ</b>\n🎮 <b>{d['title']}</b> <i>({d['year']})</i>\n\n"
    msg += f"📝 <i>{d['desc']}</i>\n\n📊 <b>ПАСПОРТ</b>\n"
    msg += f"🎭 Жанры: {d['genres_str']}\n"
    msg += f"🖥 Платформы: {d['platforms']}\n"
    msg += f"🏢 Студия: {d['dev']}\n\n" + make_hashtags(d['genres_list'])
    return msg


def build_fact(d):
    return f"💡 <b>ФАКТ ДНЯ</b>\n\n🎮 <b>{d['title']}</b>: {d['fact']}"


# === БЕСПЛАТНЫЕ ИГРЫ (GamerPower API + Epic + Reddit) ===
def get_freebies():
    print("Сбор бесплатных игр...")
    freebies = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Epic Games (прямой API)
    try:
        data = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers=headers, timeout=15).json()
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        for el in elements:
            if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                freebies.append({"title": f"🟣 [EPIC] {el.get('title')}", "link": "https://store.epicgames.com/ru/free-games", "discount": 100})
        SOURCE_STATUS["epic"] = "✅"
    except:
        SOURCE_STATUS["epic"] = "⚠️"

    # 2. GamerPower API (ВСЕ платформы: Steam, GOG, PS, Xbox и т.д.)
    try:
        gp_data = requests.get("https://www.gamerpower.com/api/giveaways?type=game", headers=headers, timeout=10).json()
        for g in gp_data[:15]:
            title = g.get("title", "")
            link = g.get("open_giveaway_url", "")
            platform = g.get("platforms", "")
            if title and link:
                emoji = "💻" if "Steam" in platform else "🟢"
                freebies.append({"title": f"{emoji} [{platform[:15]}] {title}", "link": link, "discount": 100})
        SOURCE_STATUS["gamerpower"] = "✅"
    except Exception as e:
        print(f"GamerPower сбой: {e}")
        SOURCE_STATUS["gamerpower"] = "⚠️"

    # 3. Reddit r/FreeGameFindings
    try:
        data = requests.get("https://www.reddit.com/r/FreeGameFindings/hot.json?limit=10", headers=headers, timeout=10).json()
        for post in data.get("data", {}).get("children", []):
            p = post["data"]
            if re.search(r'\b(free|100%|раздача)\b', p["title"], re.IGNORECASE):
                freebies.append({"title": f"🟢 {p['title'].strip()}", "link": "https://reddit.com" + p["permalink"], "discount": 100})
    except: pass

    return freebies[:8]


# === СКИДКИ (CheapShark + Reddit + GamerPower) ===
def get_all_deals():
    print("Сбор скидок...")
    deals = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. Steam скидки (CheapShark API - надёжно)
    try:
        cs_deals = requests.get("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=15", headers=headers, timeout=10).json()
        for d in cs_deals:
            savings = int(float(d.get("savings", 0)))
            if savings >= 50 and d.get("title"):
                steam_id = d.get("steamAppID", "")
                link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else "https://store.steampowered.com/"
                deals.append({"title": f"💻 [STEAM] {d['title']} (−{savings}%)", "link": link, "discount": savings})
        SOURCE_STATUS["cheapshark"] = "✅"
    except Exception as e:
        print(f"CheapShark сбой: {e}")
        SOURCE_STATUS["cheapshark"] = "⚠️"

    # 2. Консоли и Game Pass (Reddit r/GameDeals)
    queries = [
        ("xbox OR gamepass", "🟩 [XBOX/GP]"),
        ("psn OR playstation", "🟦 [PS]"),
        ("switch OR nintendo", "🟥 [SWITCH]")
    ]
    
    for query, emoji in queries:
        try:
            url = f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=10"
            data = requests.get(url, headers=headers, timeout=10).json()
            for post in data.get("data", {}).get("children", []):
                p = post["data"]
                title = p["title"]
                if "expired" in title.lower() or "ended" in title.lower():
                    continue
                
                discount = 0
                m = re.search(r'-\s*(\d{1,3})\s*%', title)
                if m: discount = int(m.group(1))
                elif "100%" in title.lower() or "free" in title.lower(): discount = 100
                
                if discount >= 40:
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                    deals.append({
                        "title": f"{emoji} {clean_title}",
                        "link": "https://reddit.com" + p["permalink"],
                        "discount": discount
                    })
            SOURCE_STATUS["reddit"] = "✅"
        except Exception as e:
            print(f"Reddit {query} сбой: {e}")

    # Сортировка и дедупликация
    deals.sort(key=lambda x: x["discount"], reverse=True)
    seen, unique = set(), []
    for d in deals:
        if d["link"] not in seen:
            seen.add(d["link"])
            unique.append(d)
            
    return unique[:12]


# === НОВОСТИ ===
def get_rss_news():
    news, now = [], datetime.now(timezone.utc)
    for src in RSS_SOURCES:
        try:
            for entry in feedparser.parse(src["url"]).entries[:5]:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub) < timedelta(hours=24) and entry.get("title") and entry.get("link"):
                        news.append({"title": entry["title"].strip(), "link": entry["link"], "source": src["name"]})
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

    # Пост 2: Скидки
    if deals:
        msg = "💸 <b>ГОРЯЧИЕ СКИДКИ (от 40%)</b>\n\n"
        for i, d in enumerate(deals, 1):
            msg += f"{i}. <b>{d['title']}</b>\n   🔗 <a href='{d['link']}'>Ссылка на магазин</a>\n\n"
        msg += "⏰ <i>Цены могут измениться!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)
    
    if not freebies and not deals:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо.</b>\nКрупных раздач не найдено, но мы мониторим 24/7! 🔔")
    print("Drops опубликован.")


def publish_hub_game():
    d = get_game_of_day()
    send_to_telegram(HUB_CHANNEL_ID, build_game_caption(d))
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
