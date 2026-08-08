import requests
import os
import re
import sys
import time
import feedparser
from datetime import datetime, timezone, timedelta

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
DROPS_CHANNEL_ID = os.environ.get("DROPS_CHANNEL_ID")
HUB_CHANNEL_ID = os.environ.get("HUB_CHANNEL_ID")

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("❌ ОШИБКА: Не найдены секреты!")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SEEN_ITEMS = {}
SCHEDULE = {9: "drops", 12: "hub_news", 15: "hub_gp", 18: "hub_deals", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "gamerpower": "—", "gamepass": "—", "deals": "—", "news": "—", "youtube": "—"}

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}


# === НАДЁЖНЫЙ ЗАПРОС (4 попытки) ===
def http_get(url, timeout=20, retries=4, as_json=True):
    for i in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r.json() if as_json else r.text
        except Exception as e:
            print(f"  попытка {i+1} ошибка: {e}")
        time.sleep(2 * (i + 1))
    return None


def is_duplicate(item_id):
    now = time.time()
    for k in list(SEEN_ITEMS):
        if now - SEEN_ITEMS[k] > 86400:
            del SEEN_ITEMS[k]
    if item_id in SEEN_ITEMS:
        return True
    SEEN_ITEMS[item_id] = now
    return False


def translate_to_ru(text):
    if not text:
        return ""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text[:400]}
        r = requests.get(url, params=params, timeout=6)
        if r.status_code == 200:
            return "".join([s[0] for s in r.json()[0] if s and s[0]])
    except Exception:
        pass
    return text


def send_to_telegram(chat_id, text, photo_url=None):
    if not chat_id:
        return False
    try:
        if photo_url and photo_url.startswith("http"):
            payload = {"chat_id": chat_id, "photo": photo_url, "caption": text[:1000], "parse_mode": "HTML"}
            r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=25)
        else:
            r = requests.post(TELEGRAM_URL, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"Send error: {e}")
        return False


def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except Exception:
        return "?"


# === 1. EPIC GAMES ===
def get_epic_freebies():
    print("\n🎁 EPIC...")
    freebies = []
    data = http_get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", timeout=25)
    if data:
        try:
            elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
            for el in elements:
                if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                    title = el.get("title", "")
                    if title and not is_duplicate(f"epic_{title}"):
                        image = None
                        for img in el.get("keyImages", []):
                            if img.get("type") in ["OfferImageWide", "DieselStoreFrontWide"]:
                                image = img.get("url")
                                break
                        desc = translate_to_ru(el.get("description", "Бесплатно в Epic Games Store"))[:300]
                        freebies.append({"platform": "Epic Games", "title": title, "desc": desc,
                                         "image": image, "link": "https://store.epicgames.com/ru/free-games"})
        except Exception as e:
            print(f"Epic parse error: {e}")
    SOURCE_STATUS["epic"] = "✅" if freebies else "⚠️"
    print(f"✅ Epic: {len(freebies)}")
    return freebies


# === 2. GAMERPOWER ===
def get_gamerpower_freebies():
    print("\n🎁 GAMERPOWER...")
    freebies = []
    data = http_get("https://www.gamerpower.com/api/giveaways?type=game", timeout=20)
    if isinstance(data, list):
        for g in data[:15]:
            title = g.get("title", "")
            if title and not is_duplicate(f"gp_{title}"):
                desc = translate_to_ru(g.get("description", "Бесплатная игра"))[:300]
                freebies.append({"platform": g.get("platforms", "PC"), "title": title, "desc": desc,
                                 "image": g.get("thumbnail"), "link": g.get("open_giveaway_url", "")})
    SOURCE_STATUS["gamerpower"] = "✅" if freebies else "⚠️"
    print(f"✅ GamerPower: {len(freebies)}")
    return freebies


# === 3. GAME PASS ===
def get_gamepass():
    print("\n🎮 GAME PASS...")
    games = []
    xml = http_get("https://www.reddit.com/r/XboxGamePass/.rss?limit=25", timeout=20, as_json=False)
    if xml:
        feed = feedparser.parse(xml)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            t = title.lower()
            if any(k in t for k in ["coming", "new", "added", "arriving", "game pass"]):
                if title and not is_duplicate(f"gpass_{link}"):
                    image = None
                    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                        image = entry.media_thumbnail[0].get("url")
                    games.append({"title": title, "desc": "В Xbox Game Pass", "image": image, "link": link})
                    if len(games) >= 5:
                        break
    SOURCE_STATUS["gamepass"] = "✅" if games else "⚠️"
    print(f"✅ GamePass: {len(games)}")
    return games


# === 4. СКИДКИ ===
def get_deals():
    print("\n💸 СКИДКИ...")
    deals = []

    data = http_get("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=12", timeout=20)
    if isinstance(data, list):
        for d in data:
            title = d.get("title", "")
            sid = d.get("steamAppID", "")
            sav = int(float(d.get("savings", 0)))
            if title and sid and sav >= 50 and not is_duplicate(f"steam_{sid}"):
                deals.append({"platform": "Steam", "title": title, "desc": f"Скидка {sav}%",
                              "image": None, "link": f"https://store.steampowered.com/app/{sid}/"})

    xml = http_get("https://www.reddit.com/r/GameDeals/.rss?limit=30", timeout=20, as_json=False)
    if xml:
        feed = feedparser.parse(xml)
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            tl = title.lower()
            if "expired" in tl or not link:
                continue
            m = re.search(r'-\s*(\d{1,3})\s*%', title)
            disc = int(m.group(1)) if m else 0
            if disc >= 40:
                plat = "Xbox" if "xbox" in tl else "PlayStation" if ("playstation" in tl or "psn" in tl) else "Switch" if "switch" in tl else "PC"
                if not is_duplicate(f"deal_{link}"):
                    deals.append({"platform": plat, "title": re.sub(r'^\[[^\]]*\]\s*', '', title),
                                  "desc": f"Скидка {disc}%", "image": None, "link": link})

    SOURCE_STATUS["deals"] = "✅" if deals else "⚠️"
    print(f"✅ Скидки: {len(deals)}")
    return deals[:12]


# === 5. НОВОСТИ (рус + англ с переводом) ===
def get_news():
    print("\n📰 НОВОСТИ...")
    news = []

    # Русские источники
    for src in [{"name": "DTF", "url": "https://dtf.ru/rss"},
                {"name": "StopGame", "url": "https://stopgame.ru/rss/news"},
                {"name": "3DNews", "url": "https://3dnews.ru/games/rss"}]:
        xml = http_get(src["url"], timeout=15, as_json=False, retries=2)
        if xml:
            feed = feedparser.parse(xml)
            for entry in feed.entries[:3]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if title and link and not is_duplicate(f"news_{link}"):
                    desc = re.sub(r'<[^>]+>', '', entry.get("summary", ""))[:200] if entry.get("summary") else ""
                    news.append({"title": title, "title_ru": None, "desc": desc,
                                 "link": link, "source": src["name"], "image": None})

    # Reddit r/games (англ) + перевод на русский
    xml = http_get("https://www.reddit.com/r/games/.rss?limit=20", timeout=20, as_json=False)
    if xml:
        feed = feedparser.parse(xml)
        added = 0
        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            image = None
            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                image = entry.media_thumbnail[0].get("url")
            if title and image and not is_duplicate(f"news_{link}"):
                # Переводим заголовок на русский
                title_ru = translate_to_ru(title)
                news.append({"title": title, "title_ru": title_ru, "desc": "",
                             "link": link, "source": "Reddit", "image": image})
                added += 1
                if added >= 6:
                    break

    news.sort(key=lambda x: 0 if x.get("image") else 1)
    SOURCE_STATUS["news"] = "✅" if news else "⚠️"
    print(f"✅ Новости: {len(news)}")
    return news[:10]


# === 6. YOUTUBE (user= + channel_id= fallback) ===
def get_youtube():
    print("\n🎬 YOUTUBE...")
    videos = []
    channels = [
        {"name": "Xbox", "urls": ["https://www.youtube.com/feeds/videos.xml?user=xbox",
                                  "https://www.youtube.com/feeds/videos.xml?channel_id=UCIsGQj0ZNTL3z58jzVh3j3w"]},
        {"name": "PlayStation", "urls": ["https://www.youtube.com/feeds/videos.xml?user=PlayStation",
                                         "https://www.youtube.com/feeds/videos.xml?channel_id=UC-2Y8dQb0S6Dtp6EAKKJwnw"]},
        {"name": "Nintendo", "urls": ["https://www.youtube.com/feeds/videos.xml?user=Nintendo",
                                      "https://www.youtube.com/feeds/videos.xml?channel_id=UCGIY_O-8vW4rfX98kmZ5Eew"]}
    ]
    for ch in channels:
        for url in ch["urls"]:
            xml = http_get(url, timeout=15, as_json=False, retries=2)
            if xml:
                feed = feedparser.parse(xml)
                if feed.entries:
                    e = feed.entries[0]
                    videos.append({"title": e.title.strip(), "link": e.link, "source": ch["name"]})
                    break  # этот канал сработал, идём дальше
    SOURCE_STATUS["youtube"] = "✅" if videos else "⚠️"
    print(f"✅ YouTube: {len(videos)}")
    return videos


# === ОТПРАВКА ПОСТА ===
def send_post(chat_id, item, post_type="free"):
    emoji = "🎁" if post_type == "free" else "🎮" if post_type == "gp" else "💸"
    btn = "🔗 ЗАБРАТЬ БЕСПЛАТНО" if post_type == "free" else "📖 В GAME PASS" if post_type == "gp" else "🛒 КУПИТЬ"
    text = f"{emoji} <b>{item['title']}</b>\n\n"
    if item.get("desc"):
        text += f"📝 <i>{item['desc']}</i>\n\n"
    text += f"🖥 <b>Платформа:</b> {item.get('platform', 'PC')}\n\n"
    text += f"<a href='{item['link']}'>{btn}</a>\n"
    yt = item["title"].replace(" ", "+")
    text += f"<a href='https://www.youtube.com/results?search_query={yt}'>🎬 Геймплей</a>\n\n"
    text += "━━━━━━━━━━━━━━━\n<b>🎮 AlexPlay — твой игровой помощник!</b>\n💰 @AlexPlayDrops — халява и скидки\n📰 @AlexPlayHub — новости и обзоры"
    send_to_telegram(chat_id, text, item.get("image"))


# === ПУБЛИКАЦИИ ===
def publish_drops():
    items = get_epic_freebies() + get_gamerpower_freebies()
    for it in items:
        send_post(DROPS_CHANNEL_ID, it, "free")
        time.sleep(2)
    if not items:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо</b>\n\nМониторим 24/7! 🔔")
    print(f"✅ Drops: {len(items)}")


def publish_hub_gp():
    for it in get_gamepass():
        send_post(HUB_CHANNEL_ID, it, "gp")
        time.sleep(2)


def publish_hub_deals():
    for it in get_deals():
        send_post(HUB_CHANNEL_ID, it, "deal")
        time.sleep(2)


def publish_hub_news():
    for it in get_news():
        # Если есть русский перевод — показываем оба языка красиво
        if it.get("title_ru"):
            text = f"📰 <b>НОВОСТЬ</b>\n\n🇷🇺 {it['title_ru']}\n\n🇬 {it['title']}\n\n"
        else:
            text = f"📰 <b>НОВОСТЬ</b>\n\n{it['title']}\n\n"
        if it.get("desc"):
            text += f"📝 <i>{it['desc']}</i>\n\n"
        text += f"🔗 <a href='{it['link']}'>Читать ({it['source']})</a>\n\n"
        text += "━━━━━━━━━━━━━━━\n<b>🎮 AlexPlay — твой игровой помощник!</b>\n💰 @AlexPlayDrops — халява и скидки\n📰 @AlexPlayHub — новости и обзоры"
        send_to_telegram(HUB_CHANNEL_ID, text, it.get("image"))
        time.sleep(2)


def publish_hub_video():
    vids = get_youtube()
    if vids:
        msg = "🎬 <b>ТРЕЙЛЕРЫ</b>\n\n"
        for i, v in enumerate(vids, 1):
            msg += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
        msg += "\n━━━━━━━━━━━━━━━\n<b>🎮 AlexPlay — твой игровой помощник!</b>\n💰 @AlexPlayDrops — халява и скидки\n📰 @AlexPlayHub — новости и обзоры"
        send_to_telegram(HUB_CHANNEL_ID, msg)


# === ОТЧЁТЫ ===
def send_pulse():
    if not CHAT_ID:
        return
    msg = f"📊 <b>ОТЧЁТ ALEXPLAY</b>\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f"👥 <b>@AlexPlayHub:</b> {get_chat_members(HUB_CHANNEL_ID)}\n"
    msg += f"👥 <b>@AlexPlayDrops:</b> {get_chat_members(DROPS_CHANNEL_ID)}\n\n🛰 <b>СТАТУС:</b>\n"
    for k, v in SOURCE_STATUS.items():
        msg += f"• {k.upper()}: {v}\n"
    msg += "\n" + ("✅ Всё работает!" if all(v == "✅" for v in SOURCE_STATUS.values()) else "⚠️ Есть сбои")
    send_to_telegram(CHAT_ID, msg)


def send_alert():
    if not CHAT_ID or not WARNINGS:
        return
    send_to_telegram(CHAT_ID, "🚨 <b>СБОИ</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS))


def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"{name}: {e}")
        print(f"❌ {name}: {e}")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    if mode == "auto":
        mode = SCHEDULE.get((datetime.now(timezone.utc).hour + 3) % 24, "skip")
    if mode == "skip":
        print("⏭ Пропуск")
        return
    print(f"🚀 Режим: {mode}")

    if mode in ("drops", "all"): run_safe("Drops", publish_drops)
    if mode in ("hub_gp", "all"): run_safe("HubGP", publish_hub_gp)
    if mode in ("hub_deals", "all"): run_safe("HubDeals", publish_hub_deals)
    if mode in ("hub_news", "all"): run_safe("HubNews", publish_hub_news)
    if mode in ("hub_video", "all"): run_safe("HubVideo", publish_hub_video)

    if WARNINGS: send_alert()
    if mode in ("hub_video", "all"): send_pulse()
    print("✅ Готово!")


if __name__ == "__main__":
    main()
