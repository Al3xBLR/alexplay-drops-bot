import requests
import os
import re
import sys
import json
import time
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

SCHEDULE = {9: "drops", 12: "hub_facts", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "gamerpower": "—", "cheapshark": "—", "reddit": "—", "facts": "—", "youtube": "—"}

YOUTUBE_CHANNELS = [
    {"name": "Nintendo", "feed": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"},
    {"name": "PlayStation", "feed": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
    {"name": "Xbox", "feed": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
]


def send_to_telegram(chat_id, text, photo_url=None):
    if not chat_id: 
        return False
    try:
        if photo_url:
            payload = {"chat_id": chat_id, "photo": photo_url, "caption": text[:1000], "parse_mode": "HTML"}
            r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        else:
            r = requests.post(TELEGRAM_URL, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка: {e}")
        return False


def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except: 
        return "?"


# === ХАЛЯВА (GamerPower + Epic) ===
def get_freebies():
    print("Сбор халявы...")
    freebies = []
    seen = set()
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Epic Games
    try:
        data = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers=headers, timeout=15).json()
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
        for el in elements:
            if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                title = el.get("title", "")
                if title and title not in seen:
                    seen.add(title)
                    freebies.append({
                        "title": f"🟣 [EPIC] {title}",
                        "desc": el.get("description", "Бесплатно в Epic Games Store")[:150],
                        "link": "https://store.epicgames.com/ru/free-games"
                    })
        SOURCE_STATUS["epic"] = "✅"
    except:
        SOURCE_STATUS["epic"] = "️"

    # GamerPower (все платформы)
    try:
        gp = requests.get("https://www.gamerpower.com/api/giveaways?type=game", headers=headers, timeout=10).json()
        for g in gp[:10]:
            title = g.get("title", "")
            link = g.get("open_giveaway_url", "")
            platform = g.get("platforms", "PC")
            if title and link and title not in seen:
                seen.add(title)
                freebies.append({
                    "title": f"🟢 [{platform[:15]}] {title}",
                    "desc": g.get("description", "Бесплатная игра")[:150],
                    "link": link
                })
        SOURCE_STATUS["gamerpower"] = "✅"
    except:
        SOURCE_STATUS["gamerpower"] = "⚠️"

    return freebies[:8]


# === СКИДКИ (GamerPower + CheapShark) ===
def get_deals():
    print("Сбор скидок...")
    deals = []
    seen = set()
    headers = {"User-Agent": "Mozilla/5.0"}

    # GamerPower скидки
    try:
        gp = requests.get("https://www.gamerpower.com/api/giveaways?type=game&sort=save", headers=headers, timeout=10).json()
        for g in gp[:15]:
            title = g.get("title", "")
            link = g.get("open_giveaway_url", "")
            if title and link and link not in seen:
                seen.add(link)
                deals.append({
                    "title": f"💸 {title}",
                    "desc": g.get("description", "Скидка")[:150],
                    "link": link
                })
    except: pass

    # CheapShark (Steam)
    try:
        cs = requests.get("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=10", headers=headers, timeout=10).json()
        for d in cs:
            title = d.get("title", "")
            steam_id = d.get("steamAppID", "")
            link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else ""
            savings = int(float(d.get("savings", 0)))
            if title and link and link not in seen and savings >= 50:
                seen.add(link)
                deals.append({
                    "title": f"💻 [STEAM] {title} (−{savings}%)",
                    "desc": f"Скидка {savings}%",
                    "link": link
                })
        SOURCE_STATUS["cheapshark"] = "✅"
    except:
        SOURCE_STATUS["cheapshark"] = "⚠️"

    return deals[:10]


# === ФАКТЫ ПРО ИГРЫ (Reddit r/todayilearned + r/gaming) ===
def get_game_facts():
    print("Поиск фактов...")
    facts = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        # r/todayilearned про игры
        r = requests.get("https://www.reddit.com/r/todayilearned/hot.json?limit=50", headers=headers, timeout=10)
        posts = r.json().get("data", {}).get("children", [])
        for post in posts:
            title = post["data"]["title"]
            if re.search(r'(game|video game|playstation|xbox|nintendo|steam)', title, re.IGNORECASE):
                facts.append({
                    "title": f" {title}",
                    "link": "https://reddit.com" + post["data"]["permalink"]
                })
        
        # r/gaming
        r = requests.get("https://www.reddit.com/r/gaming/hot.json?limit=20", headers=headers, timeout=10)
        posts = r.json().get("data", {}).get("children", [])
        for post in posts:
            title = post["data"]["title"]
            if "fact" in title.lower() or "did you know" in title.lower():
                facts.append({
                    "title": f"🎮 {title}",
                    "link": "https://reddit.com" + post["data"]["permalink"]
                })
        
        SOURCE_STATUS["facts"] = "✅"
    except:
        SOURCE_STATUS["facts"] = "️"

    return facts[:5]


# === НОВОСТИ С КАРТИНКАМИ (Reddit r/games) ===
def get_news_with_images():
    print("Сбор новостей...")
    news = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get("https://www.reddit.com/r/games/hot.json?limit=15", headers=headers, timeout=10)
        posts = r.json().get("data", {}).get("children", [])
        for post in posts:
            p = post["data"]
            title = p["title"]
            link = "https://reddit.com" + p["permalink"]
            thumbnail = p.get("thumbnail", "")
            
            # Пропускаем self-посты и не картинки
            if thumbnail and thumbnail != "self" and thumbnail != "default" and thumbnail != "nsfw":
                news.append({
                    "title": title,
                    "link": link,
                    "image": thumbnail if thumbnail.startswith("http") else None
                })
        
        SOURCE_STATUS["reddit"] = "✅"
    except:
        SOURCE_STATUS["reddit"] = "️"

    return news[:5]


# === YOUTUBE ===
def get_youtube_videos():
    videos = []
    try:
        import feedparser
        for ch in YOUTUBE_CHANNELS:
            feed = feedparser.parse(ch["feed"])
            for entry in feed.entries[:1]:
                if entry.get("title") and entry.get("link"):
                    videos.append({
                        "title": entry["title"].strip(),
                        "link": entry["link"],
                        "source": ch["name"]
                    })
        SOURCE_STATUS["youtube"] = "✅"
    except:
        SOURCE_STATUS["youtube"] = "️"
    return videos[:3]


# === ПУБЛИКАЦИЯ ===
def publish_drops():
    freebies = get_freebies()
    deals = get_deals()

    if freebies:
        msg = "🔥 <b>БЕСПЛАТНЫЕ ИГРЫ!</b>\n\n"
        for i, f in enumerate(freebies, 1):
            msg += f"{i}. <b>{f['title']}</b>\n   📝 <i>{f['desc']}</i>\n"
            msg += f"   🔗 <a href='{f['link']}'>Забрать</a>\n"
            msg += f"    <a href='https://www.youtube.com/results?search_query={f['title'].replace(' ', '+')}+геймплей'>Геймплей</a>\n\n"
        send_to_telegram(DROPS_CHANNEL_ID, msg)

    if deals:
        msg = "💸 <b>СКИДКИ</b>\n\n"
        for i, d in enumerate(deals, 1):
            msg += f"{i}. <b>{d['title']}</b>\n   📝 <i>{d['desc']}</i>\n"
            msg += f"   🔗 <a href='{d['link']}'>Купить</a>\n\n"
        send_to_telegram(DROPS_CHANNEL_ID, msg)
    
    if not freebies and not deals:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 Пока тихо. Мониторим 24/7! 🔔")
    print("Drops OK")


def publish_hub_facts():
    facts = get_game_facts()
    if facts:
        for f in facts:
            send_to_telegram(HUB_CHANNEL_ID, f"🎮 <b>ФАКТ ДНЯ</b>\n\n{f['title']}\n\n🔗 <a href='{f['link']}'>Обсудить на Reddit</a>")
    else:
        send_to_telegram(HUB_CHANNEL_ID, " <b>ФАКТ ДНЯ</b>\n\nИнтересный факт: первая видеоигра была создана в 1958 году и называлась Tennis for Two.\n\n<i>Завтра будет новый факт!</i>")
    print("Facts OK")


def publish_hub_news():
    news = get_news_with_images()
    if not news:
        return
    
    for n in news:
        msg = f" <b>НОВОСТЬ</b>\n\n{n['title']}\n\n <a href='{n['link']}'>Читать на Reddit</a>"
        send_to_telegram(HUB_CHANNEL_ID, msg, n["image"])
    print("News OK")


def publish_hub_steam():
    # Новинки Steam
    try:
        import feedparser
        feed = feedparser.parse("https://store.steampowered.com/feeds/newreleases/")
        if feed.entries:
            entry = feed.entries[0]
            msg = f"🆕 <b>НОВИНКА STEAM</b>\n\n{entry.title}\n\n <a href='{entry.link}'>Страница в Steam</a>"
            send_to_telegram(HUB_CHANNEL_ID, msg)
            SOURCE_STATUS["steam"] = "✅"
    except:
        SOURCE_STATUS["steam"] = "️"
    print("Steam OK")


def publish_hub_video():
    vids = get_youtube_videos()
    if vids:
        msg = "🎬 <b>ТРЕЙЛЕРЫ</b>\n\n"
        for i, v in enumerate(vids, 1):
            msg += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
        send_to_telegram(HUB_CHANNEL_ID, msg)
    print("Video OK")


# === ОТЧЁТЫ ===
def send_pulse():
    if not CHAT_ID: 
        return
    msg = f"📊 <b>Отчёт AlexPlay</b>\n {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f"👥 Hub: <b>{get_chat_members(HUB_CHANNEL_ID)}</b>\n"
    msg += f"👥 Drops: <b>{get_chat_members(DROPS_CHANNEL_ID)}</b>\n\n🛰 Статус:\n"
    for k, v in SOURCE_STATUS.items():
        msg += f"• {k.upper()}: {v}\n"
    msg += "\n✅ Всё работает!" if all(x=="✅" for x in SOURCE_STATUS.values()) else "\n️ Есть сбои."
    send_to_telegram(CHAT_ID, msg)


def send_alert():
    if not CHAT_ID or not WARNINGS: 
        return
    msg = " <b>Сбои:</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS)
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
    
    if mode == "skip": 
        return
    
    if mode in ("drops", "all"): 
        run_safe("Drops", publish_drops)
    if mode in ("hub_facts", "all"): 
        run_safe("HubFacts", publish_hub_facts)
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
