import requests
import os
import re
import sys
import json
import time
import random
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("ОШИБКА: Не найдены секреты!")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SCHEDULE = {9: "drops", 12: "hub_quiz", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "gamerpower": "—", "cheapshark": "—", "reddit": "—", "rss": "—", "youtube": "—"}

# === КВИЗЫ (вместо скучной игры дня) ===
QUIZZES = [
    {"q": "В этой игре ты играешь за ведьмака, который ищет приёмную дочь. Какой это серии игр?", "a": "The Witcher (Ведьмак)", "genre": "RPG"},
    {"q": "Эта игра про выживание в постапокалипсисе с зомби. Игрок может строить укрепления и крафтить оружие. Что это?", "a": "7 Days to Die / State of Decay", "genre": "Выживание"},
    {"q": "В этой игре весь геймплей снят одним непрерывным планом без склеек. О какой игре речь?", "a": "God of War (2018)", "genre": "Экшен"},
    {"q": "Эта игра стала самой продаваемой в истории, обойдя все остальные. Что это?", "a": "Minecraft", "genre": "Песочница"},
    {"q": "В этой игре нельзя двигаться, но можно управлять временем. Что это?", "a": "Superhot", "genre": "Шутер"},
    {"q": "Эта игра про ферму, которую один человек разрабатывал 4 года в одиночку. Что это?", "a": "Stardew Valley", "genre": "Симулятор"},
    {"q": "В этой игре все боссы — это боги скандинавской мифологии. О чём речь?", "a": "God of War", "genre": "Экшен"},
    {"q": "Эта игра про побег из преисподней, где каждая попытка уникальна. Что это?", "a": "Hades", "genre": "Рогалик"},
    {"q": "В этой игре физический движок позволяет строить любые механизмы. Что это?", "a": "Breath of the Wild / Tears of the Kingdom", "genre": "Приключение"},
    {"q": "Эта игра про детектива с амнезией, который расследует убийство. Что это?", "a": "L.A. Noire", "genre": "Детектив"},
    {"q": "В этой игре весь мир — это одна большая головоломка с петлёй времени. Что это?", "a": "Outer Wilds", "genre": "Приключение"},
    {"q": "Эта игра про гонки на выживание с оружием на аренах. Что это?", "a": "Twisted Metal", "genre": "Гонки"},
    {"q": "В этой игре ты управляешь цивилизацией от каменного века до космоса. Что это?", "a": "Civilization", "genre": "Стратегия"},
    {"q": "Эта игра про вампира в готическом Лондоне с охотниками на чудовищ. Что это?", "a": "Bloodborne", "genre": "RPG"},
    {"q": "В этой игре можно пройти, не убив ни одного врага. Что это?", "a": "Undertale", "genre": "RPG"},
]

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


def send_to_telegram(chat_id, text, photo_url=None):
    if not chat_id: return False
    try:
        if photo_url:
            payload = {"chat_id": chat_id, "photo": photo_url, "caption": text[:1000], "parse_mode": "HTML"}
            r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        else:
            r = requests.post(TELEGRAM_URL, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False


def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except: return "?"


def fmt_num(n): return f"{int(n):,}".replace(",", " ") if n else "0"


# === ХАЛЯВА С ОПИСАНИЯМИ И БЕЗ ДУБЛЕЙ ===
def get_freebies():
    print("Сбор бесплатных игр...")
    freebies = []
    seen_titles = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1. Epic Games
    try:
        data = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers=headers, timeout=15).json()
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        for el in elements:
            if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                title = el.get("title", "")
                desc = el.get("description", "") or el.get("seller", {}).get("name", "")
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    freebies.append({
                        "title": f"🟣 [EPIC] {title}",
                        "desc": desc[:150] if desc else "Бесплатная игра в Epic Games Store",
                        "link": "https://store.epicgames.com/ru/free-games",
                        "platform": "Epic Games"
                    })
        SOURCE_STATUS["epic"] = "✅"
    except Exception as e:
        print(f"Epic сбой: {e}")
        SOURCE_STATUS["epic"] = "⚠️"

    # 2. GamerPower API (все платформы)
    try:
        gp_data = requests.get("https://www.gamerpower.com/api/giveaways?type=game", headers=headers, timeout=10).json()
        for g in gp_data[:20]:
            title = g.get("title", "")
            desc = g.get("description", "") or g.get("open_giveaway", "")
            platform = g.get("platforms", "PC")
            link = g.get("open_giveaway_url", "")
            
            if title and title not in seen_titles and link:
                seen_titles.add(title)
                emoji = "💻" if "Steam" in platform else "🟢"
                freebies.append({
                    "title": f"{emoji} [{platform[:20]}] {title}",
                    "desc": desc[:150] if desc else "Бесплатная игра",
                    "link": link,
                    "platform": platform
                })
        SOURCE_STATUS["gamerpower"] = "✅"
    except Exception as e:
        print(f"GamerPower сбой: {e}")
        SOURCE_STATUS["gamerpower"] = "⚠️"

    return freebies[:10]


# === СКИДКИ С ИСПРАВЛЕНИЯМИ ===
def get_all_deals():
    print("Сбор скидок...")
    deals = []
    seen_links = set()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. Steam (CheapShark API)
    try:
        for attempt in range(3):
            try:
                cs_deals = requests.get("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=15", headers=headers, timeout=10).json()
                for d in cs_deals:
                    savings = int(float(d.get("savings", 0)))
                    title = d.get("title", "")
                    steam_id = d.get("steamAppID", "")
                    link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else "https://store.steampowered.com/"
                    
                    if title and savings >= 50 and link not in seen_links:
                        seen_links.add(link)
                        deals.append({
                            "title": f"💻 [STEAM] {title}",
                            "desc": f"Скидка {savings}% на игру в Steam",
                            "link": link,
                            "discount": savings
                        })
                SOURCE_STATUS["cheapshark"] = "✅"
                break
            except:
                if attempt == 2:
                    raise
                time.sleep(2)
    except Exception as e:
        print(f"CheapShark сбой: {e}")
        SOURCE_STATUS["cheapshark"] = "⚠️"

    # 2. Консоли (Reddit r/GameDeals)
    queries = [
        ("xbox OR gamepass", "🟩 [XBOX]"),
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
                link = "https://reddit.com" + p["permalink"]
                
                if "expired" in title.lower() or link in seen_links:
                    continue
                
                discount = 0
                m = re.search(r'-\s*(\d{1,3})\s*%', title)
                if m: discount = int(m.group(1))
                elif "100%" in title.lower(): discount = 100
                
                if discount >= 40:
                    seen_links.add(link)
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                    deals.append({
                        "title": f"{emoji} {clean_title}",
                        "desc": f"Скидка {discount}% на {query.split()[0]}",
                        "link": link,
                        "discount": discount
                    })
            SOURCE_STATUS["reddit"] = "✅"
        except Exception as e:
            print(f"Reddit {query} сбой: {e}")

    deals.sort(key=lambda x: x["discount"], reverse=True)
    return deals[:12]


# === ИГРОВОЙ КВИЗ (вместо игры дня) ===
def get_daily_quiz():
    day = datetime.now().timetuple().tm_yday
    quiz = QUIZZES[day % len(QUIZZES)]
    return quiz


def build_quiz_post(quiz):
    msg = "🎮 <b>ИГРОВОЙ КВИЗ</b>\n\n"
    msg += f"❓ <b>{quiz['q']}</b>\n\n"
    msg += f" Жанр: <i>{quiz['genre']}</i>\n\n"
    msg += "💬 <i>Пиши ответ в комментариях! Правильный ответ завтра.</i>\n\n"
    msg += " <i>Подпишись на @AlexPlayDrops, чтобы не пропустить халяву!</i>"
    return msg


def build_quiz_answer(quiz):
    return f"✅ <b>Правильный ответ:</b>\n\n🎮 <b>{quiz['a']}</b>\n\n🎯 Жанр: {quiz['genre']}\n\nХочешь ещё квизов? Пиши в комментарии!"


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

    # Пост 1: Халява с описаниями и кнопками YouTube
    if freebies:
        msg = " <b>БЕСПЛАТНЫЕ ИГРЫ ПРЯМО СЕЙЧАС!</b>\n\n"
        for i, f in enumerate(freebies, 1):
            youtube_search = f["title"].replace("🟣 [EPIC] ", "").replace("💻 [Steam] ", "").strip()
            msg += f"{i}. <b>{f['title']}</b>\n"
            msg += f"   📝 <i>{f['desc']}</i>\n"
            msg += f"   🔗 <a href='{f['link']}'>Забрать бесплатно</a>\n"
            msg += f"   🎬 <a href='https://www.youtube.com/results?search_query={youtube_search.replace(' ', '+')}+геймплей'>Смотреть геймплей</a>\n\n"
        msg += "⏰ <i>Количество ограничено!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)

    # Пост 2: Скидки
    if deals:
        msg = "💸 <b>ГОРЯЧИЕ СКИДКИ (от 40%)</b>\n\n"
        for i, d in enumerate(deals, 1):
            youtube_search = re.sub(r'💻 \[STEAM\] |🟩 \[XBOX\] |🟦 \[PS\] |🟥 \[SWITCH\] ', '', d["title"]).strip()
            msg += f"{i}. <b>{d['title']}</b>\n"
            msg += f"   📝 <i>{d['desc']}</i>\n"
            msg += f"   🔗 <a href='{d['link']}'>Купить со скидкой</a>\n"
            msg += f"    <a href='https://www.youtube.com/results?search_query={youtube_search.replace(' ', '+')}+обзор'>Смотреть обзор</a>\n\n"
        msg += "⏰ <i>Цены могут измениться!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)
    
    if not freebies and not deals:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо.</b>\nКрупных раздач не найдено, но мы мониторим 24/7! 🔔")
    print("Drops опубликован.")


def publish_hub_quiz():
    quiz = get_daily_quiz()
    # Завчерашний ответ (для тех, кто подписался недавно)
    yesterday_quiz = QUIZZES[(datetime.now().timetuple().tm_yday - 1) % len(QUIZZES)]
    
    send_to_telegram(HUB_CHANNEL_ID, build_quiz_answer(yesterday_quiz))
    send_to_telegram(HUB_CHANNEL_ID, build_quiz_post(quiz))
    print("Hub Quiz опубликован.")


def publish_hub_news():
    news = get_rss_news()
    if not news: return
    msg = " <b>ГЛАВНЫЕ НОВОСТИ</b>\n\n"
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
    msg += "🔔 <i>Подпишись на @AlexPlayDrops!</i>"
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
    msg += "\n✅ Всё работает!" if all(x=="✅" for x in SOURCE_STATUS.values()) else "\n⚠️ Есть сбои."
    send_to_telegram(CHAT_ID, msg)


def send_alert():
    if not CHAT_ID or not WARNINGS: return
    msg = "🚨 <b>Сбои в боте:</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS)
    send_to_telegram(CHAT_ID, msg[:4000])


def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"СБОЙ {name}: {e}")
        print(f"Сбой {name}: {e}")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    if mode == "auto":
        mode = SCHEDULE.get((datetime.now(timezone.utc).hour + 3) % 24, "skip")
    
    if mode == "skip": return
    
    if mode in ("drops", "all"): run_safe("Drops", publish_drops)
    if mode in ("hub_quiz", "all"): run_safe("HubQuiz", publish_hub_quiz)
    if mode in ("hub_news", "all"): run_safe("HubNews", publish_hub_news)
    if mode in ("hub_video", "all"): run_safe("HubVideo", publish_hub_video)
    
    if WARNINGS: send_alert()
    if mode in ("hub_video", "all"): send_pulse()


if __name__ == "__main__":
    main()
