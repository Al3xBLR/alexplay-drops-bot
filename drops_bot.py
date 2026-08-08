import requests
import os
import re
import sys
import json
import time
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("❌ ОШИБКА: Не найдены секреты!")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SCHEDULE = {
    9: "drops",        # 12:00 МСК - халява
    12: "hub_news",    # 15:00 МСК - новости
    15: "hub_gp",      # 18:00 МСК - Game Pass
    18: "hub_deals",   # 21:00 МСК - скидки
    21: "hub_video"    # 00:00 МСК - трейлеры
}

WARNINGS = []
SOURCE_STATUS = {
    "epic": "—", "gamerpower": "—", "gamepass": "—",
    "deals": "—", "news_ru": "—", "news_en": "—", "youtube": "—"
}

# === НАДЁЖНЫЙ HTTP ЗАПРОС ===
def safe_request(url, timeout=15, retries=3):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception as e:
            if i < retries - 1:
                time.sleep(2)
    return None


# === ХАЛЯВА С КАРТИНКАМИ ===
def get_freebies():
    print(" Сбор бесплатных игр...")
    freebies = []
    seen = set()
    
    # Epic Games
    r = safe_request("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions")
    if r:
        try:
            data = r.json()
            elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
            for el in elements:
                if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                    title = el.get("title", "")
                    if title and title not in seen:
                        seen.add(title)
                        image = None
                        if el.get("keyImages"):
                            for img in el["keyImages"]:
                                if img.get("type") == "DieselStoreFrontWide":
                                    image = img.get("url")
                                    break
                        freebies.append({
                            "platform": "Epic Games",
                            "title": title,
                            "desc": el.get("description", "Бесплатно в Epic Games Store")[:250],
                            "image": image,
                            "link": "https://store.epicgames.com/ru/free-games"
                        })
            SOURCE_STATUS["epic"] = "✅"
        except Exception as e:
            print(f"Epic error: {e}")
            SOURCE_STATUS["epic"] = "⚠️"
    
    # GamerPower
    r = safe_request("https://www.gamerpower.com/api/giveaways?type=game")
    if r:
        try:
            for g in r.json()[:10]:
                title = g.get("title", "")
                if title and title not in seen:
                    seen.add(title)
                    freebies.append({
                        "platform": g.get("platforms", "PC"),
                        "title": title,
                        "desc": g.get("description", "Бесплатная игра")[:250],
                        "image": g.get("thumbnail"),
                        "link": g.get("open_giveaway_url", "")
                    })
            SOURCE_STATUS["gamerpower"] = "✅"
        except Exception as e:
            print(f"GamerPower error: {e}")
            SOURCE_STATUS["gamerpower"] = "⚠️"
    
    return freebies


# === GAME PASS ===
def get_gamepass():
    print("🎮 Сбор Game Pass...")
    games = []
    
    # Reddit r/XboxGamePass
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get("https://www.reddit.com/r/XboxGamePass/hot.json?limit=15", 
                        headers=headers, timeout=10)
        if r.status_code == 200:
            posts = r.json().get("data", {}).get("children", [])
            for post in posts:
                p = post["data"]
                title = p["title"]
                if any(x in title.lower() for x in ["coming", "new", "added", "june", "july", "august"]):
                    games.append({
                        "title": title,
                        "desc": "Скоро или уже в Game Pass",
                        "image": p.get("thumbnail") if p.get("thumbnail") and not p.get("thumbnail").startswith("self") else None,
                        "link": "https://reddit.com" + p["permalink"]
                    })
        SOURCE_STATUS["gamepass"] = "✅"
    except Exception as e:
        print(f"GamePass error: {e}")
        SOURCE_STATUS["gamepass"] = "⚠️"
    
    return games[:5]


# === СКИДКИ ===
def get_all_deals():
    print("💸 Сбор скидок...")
    deals = []
    seen = set()
    
    # CheapShark Steam
    r = safe_request("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=10")
    if r:
        try:
            for d in r.json():
                title = d.get("title", "")
                steam_id = d.get("steamAppID", "")
                link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else ""
                savings = int(float(d.get("savings", 0)))
                if title and link and link not in seen and savings >= 50:
                    seen.add(link)
                    deals.append({
                        "platform": "Steam",
                        "title": title,
                        "desc": f"Скидка {savings}% • Обычная цена: ${d.get('normalPrice', 'N/A')}",
                        "image": None,
                        "link": link
                    })
            SOURCE_STATUS["deals"] = "✅"
        except Exception as e:
            print(f"CheapShark error: {e}")
            SOURCE_STATUS["deals"] = "️"
    
    # Reddit GameDeals
    headers = {"User-Agent": "Mozilla/5.0"}
    queries = [("xbox", "Xbox"), ("playstation", "PlayStation"), ("switch", "Nintendo Switch")]
    
    for query, platform in queries:
        try:
            url = f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=5"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                for post in r.json().get("data", {}).get("children", []):
                    p = post["data"]
                    title = p["title"]
                    link = "https://reddit.com" + p["permalink"]
                    
                    if "expired" in title.lower() or link in seen:
                        continue
                    
                    m = re.search(r'-\s*(\d{1,3})\s*%', title)
                    discount = int(m.group(1)) if m else 50
                    
                    if discount >= 40:
                        seen.add(link)
                        deals.append({
                            "platform": platform,
                            "title": re.sub(r'^\[[^\]]*\]\s*', '', title),
                            "desc": f"Скидка {discount}%",
                            "image": None,
                            "link": link
                        })
        except: pass
    
    deals.sort(key=lambda x: x.get("platform", "") == "Steam", reverse=True)
    return deals[:10]


# === НОВОСТИ (РУССКИЕ + АНГЛИЙСКИЕ ИСТОЧНИКИ) ===
def get_all_news():
    print("📰 Сбор новостей...")
    news = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Русские источники
    ru_sources = [
        {"name": "DTF", "url": "https://dtf.ru/rss"},
        {"name": "StopGame", "url": "https://stopgame.ru/rss/news"},
        {"name": "3DNews", "url": "https://3dnews.ru/games/rss"},
        {"name": "Kanobu", "url": "https://www.kanobu.ru/rss/news/"}
    ]
    
    for src in ru_sources:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:3]:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - pub) < timedelta(hours=48):
                        news.append({
                            "title": f"{entry.title}",
                            "desc": entry.get("summary", "")[:200] if entry.get("summary") else "",
                            "link": entry.link,
                            "source": src["name"],
                            "image": None,
                            "lang": "ru"
                        })
            SOURCE_STATUS["news_ru"] = "✅"
        except Exception as e:
            print(f"RSS {src['name']} error: {e}")
            SOURCE_STATUS["news_ru"] = "⚠️"
    
    # Reddit r/games
    try:
        r = requests.get("https://www.reddit.com/r/games/hot.json?limit=20", 
                        headers=headers, timeout=10)
        if r.status_code == 200:
            for post in r.json().get("data", {}).get("children", [])[:5]:
                p = post["data"]
                thumb = p.get("thumbnail", "")
                news.append({
                    "title": p["title"],
                    "desc": "",
                    "link": "https://reddit.com" + p["permalink"],
                    "source": "Reddit r/games",
                    "image": thumb if thumb and thumb.startswith("http") else None,
                    "lang": "en"
                })
            SOURCE_STATUS["news_en"] = "✅"
    except Exception as e:
        print(f"Reddit error: {e}")
        SOURCE_STATUS["news_en"] = "⚠️"
    
    # Сортировка: сначала с картинками
    news.sort(key=lambda x: 0 if x.get("image") else 1)
    return news[:10]


# === YOUTUBE ===
def get_youtube_videos():
    print("🎬 Сбор трейлеров...")
    videos = []
    channels = [
        {"name": "Xbox", "url": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
        {"name": "PlayStation", "url": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
        {"name": "Nintendo", "url": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"}
    ]
    
    try:
        for ch in channels:
            feed = feedparser.parse(ch["url"])
            for entry in feed.entries[:1]:
                videos.append({
                    "title": entry.title.strip(),
                    "link": entry.link,
                    "source": ch["name"]
                })
        SOURCE_STATUS["youtube"] = "✅"
    except Exception as e:
        print(f"YouTube error: {e}")
        SOURCE_STATUS["youtube"] = "⚠️"
    
    return videos[:3]


# === ОТПРАВКА КРАСИВОГО ПОСТА ===
def send_beautiful_post(chat_id, item, post_type="free"):
    if post_type == "free":
        emoji = "🎁"
        btn_text = " ЗАБРАТЬ БЕСПЛАТНО"
    elif post_type == "gamepass":
        emoji = "🎮"
        btn_text = "📖 В GAME PASS"
    else:
        emoji = "💸"
        btn_text = "🛒 КУПИТЬ"
    
    text = f"{emoji} <b>{item['title']}</b>\n\n"
    if item.get("desc"):
        text += f" <i>{item['desc']}</i>\n\n"
    text += f" <b>Платформа:</b> {item.get('platform', 'PC')}\n\n"
    text += f"<a href='{item['link']}'>{btn_text}</a>"
    
    # YouTube ссылка
    yt_query = item["title"].replace(" ", "+")
    text += f" | <a href='https://www.youtube.com/results?search_query={yt_query}'>🎬 Геймплей</a>"
    
    send_to_telegram(chat_id, text, item.get("image"))


def send_to_telegram(chat_id, text, photo_url=None):
    if not chat_id:
        return False
    try:
        if photo_url and photo_url.startswith("http"):
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": text[:1000],
                "parse_mode": "HTML"
            }
            r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        else:
            r = requests.post(TELEGRAM_URL, data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Send error: {e}")
        return False


def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", 
                        params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except:
        return "?"


# === ПУБЛИКАЦИИ ===
def publish_drops():
    freebies = get_freebies()
    for fb in freebies:
        send_beautiful_post(DROPS_CHANNEL_ID, fb, "free")
        time.sleep(1)
    print(f"✅ Drops: {len(freebies)} игр")


def publish_hub_gp():
    games = get_gamepass()
    for g in games:
        send_beautiful_post(HUB_CHANNEL_ID, g, "gamepass")
        time.sleep(1)
    print(f"✅ GamePass: {len(games)} игр")


def publish_hub_deals():
    deals = get_all_deals()
    for d in deals:
        send_beautiful_post(HUB_CHANNEL_ID, d, "deal")
        time.sleep(1)
    print(f"✅ Deals: {len(deals)} скидок")


def publish_hub_news():
    news = get_all_news()
    for n in news:
        text = f"📰 <b>НОВОСТЬ</b>\n\n{n['title']}\n\n"
        if n.get("desc"):
            text += f"📝 <i>{n['desc']}</i>\n\n"
        text += f"🔗 <a href='{n['link']}'>Читать ({n['source']})</a>"
        send_to_telegram(HUB_CHANNEL_ID, text, n.get("image"))
        time.sleep(1)
    print(f"✅ News: {len(news)} новостей")


def publish_hub_video():
    videos = get_youtube_videos()
    if videos:
        msg = "🎬 <b>СВЕЖИЕ ТРЕЙЛЕРЫ</b>\n\n"
        for i, v in enumerate(videos, 1):
            msg += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
        msg += "\n🔔 <i>Подпишись на @AlexPlayDrops — там халява!</i>"
        send_to_telegram(HUB_CHANNEL_ID, msg)
    print(f"✅ Video: {len(videos)} трейлеров")


# === ОТЧЁТЫ ===
def send_pulse():
    if not CHAT_ID:
        return
    msg = f"📊 <b>ОТЧЁТ ALEXPLAY</b>\n {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f"👥 <b>@AlexPlayHub:</b> {get_chat_members(HUB_CHANNEL_ID)}\n"
    msg += f" <b>@AlexPlayDrops:</b> {get_chat_members(DROPS_CHANNEL_ID)}\n\n"
    msg += "🛰 <b>СТАТУС:</b>\n"
    for k, v in SOURCE_STATUS.items():
        msg += f"• {k.upper()}: {v}\n"
    msg += "\n" + ("✅ Всё работает!" if all(v=="✅" for v in SOURCE_STATUS.values()) else "⚠️ Есть сбои")
    send_to_telegram(CHAT_ID, msg)


def send_alert():
    if not CHAT_ID or not WARNINGS:
        return
    msg = "🚨 <b>СБОИ</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS)
    send_to_telegram(CHAT_ID, msg[:4000])


def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"{name}: {str(e)}")
        print(f"❌ {name}: {e}")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    if mode == "auto":
        mode = SCHEDULE.get((datetime.now(timezone.utc).hour + 3) % 24, "skip")
    
    if mode == "skip":
        return
    
    if mode in ("drops", "all"):
        run_safe("Drops", publish_drops)
    if mode in ("hub_gp", "all"):
        run_safe("HubGP", publish_hub_gp)
    if mode in ("hub_deals", "all"):
        run_safe("HubDeals", publish_hub_deals)
    if mode in ("hub_news", "all"):
        run_safe("HubNews", publish_hub_news)
    if mode in ("hub_video", "all"):
        run_safe("HubVideo", publish_hub_video)
    
    if WARNINGS:
        send_alert()
    if mode in ("hub_video", "all"):
        send_pulse()


if __name__ == "__main__":
    main()
