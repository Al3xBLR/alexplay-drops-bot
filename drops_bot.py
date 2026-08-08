import requests
import os
import re
import sys
import json
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


def is_duplicate(item_id):
    now = time.time()
    SEEN_ITEMS = {k: v for k, v in SEEN_ITEMS.items() if now - v < 86400}
    if item_id in SEEN_ITEMS:
        return True
    SEEN_ITEMS[item_id] = now
    return False


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
    except:
        return "?"


# === 1. EPIC GAMES ===
def get_epic_freebies():
    print("\n🎁 EPIC GAMES...")
    freebies = []
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers=headers, timeout=25)
        
        if r.status_code == 200:
            data = r.json()
            elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
            
            for el in elements:
                if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                    title = el.get("title", "")
                    if title and not is_duplicate(f"epic_{title}"):
                        image = None
                        for img in el.get("keyImages", []):
                            if img.get("type") in ["OfferImageWide", "DieselStoreFrontWide"]:
                                image = img.get("url")
                                break
                        
                        freebies.append({
                            "platform": "Epic Games",
                            "title": title,
                            "desc": el.get("description", "Бесплатно")[:300],
                            "image": image,
                            "link": "https://store.epicgames.com/ru/free-games"
                        })
            
            SOURCE_STATUS["epic"] = "✅"
            print(f"✅ Epic: {len(freebies)} игр")
    except Exception as e:
        print(f"❌ Epic: {e}")
        SOURCE_STATUS["epic"] = "⚠️"
    
    return freebies


# === 2. GAMERPOWER ===
def get_gamerpower_freebies():
    print("\n🎁 GAMERPOWER...")
    freebies = []
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.gamerpower.com/api/giveaways?type=game", headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            for g in data[:15]:
                title = g.get("title", "")
                platform = g.get("platforms", "PC")
                
                if title and not is_duplicate(f"gp_{title}"):
                    freebies.append({
                        "platform": platform,
                        "title": title,
                        "desc": g.get("description", "Бесплатная игра")[:300],
                        "image": g.get("thumbnail"),
                        "link": g.get("open_giveaway_url", "")
                    })
            
            SOURCE_STATUS["gamerpower"] = "✅"
            print(f"✅ GamerPower: {len(freebies)} игр")
    except Exception as e:
        print(f"❌ GamerPower: {e}")
        SOURCE_STATUS["gamerpower"] = "️"
    
    return freebies


# === 3. GAME PASS (ИСПРАВЛЕНО) ===
def get_gamepass():
    print("\n🎮 GAME PASS...")
    games = []
    
    try:
        # Используем правильный User-Agent для Reddit
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # Пробуем hot posts
        url = "https://www.reddit.com/r/XboxGamePass/hot.json?limit=30"
        r = requests.get(url, headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            posts = data.get("data", {}).get("children", [])
            
            print(f"  Найдено постов: {len(posts)}")
            
            for post in posts:
                p = post.get("data", {})
                title = p.get("title", "")
                post_id = p.get("id", "")
                
                # Ищем ключевые слова
                title_lower = title.lower()
                keywords = ["coming", "new", "added", "arriving", "june", "july", "august", "september", "october"]
                
                if any(kw in title_lower for kw in keywords):
                    if not is_duplicate(f"gp_{post_id}"):
                        # Извлекаем картинку
                        image = None
                        thumb = p.get("thumbnail", "")
                        
                        if thumb and thumb.startswith("http") and thumb != "self" and thumb != "default":
                            image = thumb
                        elif p.get("preview"):
                            imgs = p["preview"].get("images", [])
                            if imgs:
                                image = imgs[0].get("source", {}).get("url")
                        
                        games.append({
                            "title": title,
                            "desc": "В Xbox Game Pass",
                            "image": image,
                            "link": f"https://reddit.com{p.get('permalink', '')}"
                        })
                        
                        print(f"  ✅ {title[:60]}")
                        
                        if len(games) >= 5:
                            break
            
            SOURCE_STATUS["gamepass"] = "✅"
            print(f"✅ Game Pass: {len(games)} игр")
        else:
            print(f"❌ Reddit API: статус {r.status_code}")
            SOURCE_STATUS["gamepass"] = "⚠️"
    
    except Exception as e:
        print(f"❌ Game Pass: {e}")
        SOURCE_STATUS["gamepass"] = "️"
    
    return games


# === 4. СКИДКИ (ИСПРАВЛЕНО) ===
def get_deals():
    print("\n💸 СКИДКИ...")
    deals = []
    
    # 1. CheapShark (Steam)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=15", headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            for d in data:
                title = d.get("title", "")
                steam_id = d.get("steamAppID", "")
                savings = float(d.get("savings", 0))
                
                if title and steam_id and savings >= 50:
                    if not is_duplicate(f"steam_{steam_id}"):
                        deals.append({
                            "platform": "Steam",
                            "title": title,
                            "desc": f"Скидка {int(savings)}%",
                            "image": None,
                            "link": f"https://store.steampowered.com/app/{steam_id}/"
                        })
                        print(f"  ✅ Steam: {title[:40]} (-{int(savings)}%)")
            
            SOURCE_STATUS["deals"] = "✅"
    except Exception as e:
        print(f"❌ CheapShark: {e}")
        SOURCE_STATUS["deals"] = "⚠️"
    
    # 2. Reddit GameDeals
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        queries = [
            ("xbox", "Xbox"),
            ("playstation", "PlayStation"),
            ("switch", "Nintendo Switch")
        ]
        
        for query, platform in queries:
            url = f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=5"
            r = requests.get(url, headers=headers, timeout=15)
            
            if r.status_code == 200:
                data = r.json()
                posts = data.get("data", {}).get("children", [])
                
                for post in posts:
                    p = post.get("data", {})
                    title = p.get("title", "")
                    permalink = p.get("permalink", "")
                    
                    if "expired" in title.lower() or not permalink:
                        continue
                    
                    # Извлекаем процент
                    m = re.search(r'-\s*(\d{1,3})\s*%', title)
                    discount = int(m.group(1)) if m else 50
                    
                    if discount >= 40:
                        if not is_duplicate(f"reddit_{permalink}"):
                            clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                            deals.append({
                                "platform": platform,
                                "title": clean_title,
                                "desc": f"Скидка {discount}%",
                                "image": None,
                                "link": f"https://reddit.com{permalink}"
                            })
                            print(f"  ✅ {platform}: {clean_title[:40]} (-{discount}%)")
    
    except Exception as e:
        print(f"❌ Reddit deals: {e}")
    
    print(f"✅ Всего скидок: {len(deals)}")
    return deals


# === 5. НОВОСТИ (ИСПРАВЛЕНО) ===
def get_news():
    print("\n📰 НОВОСТИ...")
    news = []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        url = "https://www.reddit.com/r/games/hot.json?limit=30"
        r = requests.get(url, headers=headers, timeout=20)
        
        if r.status_code == 200:
            data = r.json()
            posts = data.get("data", {}).get("children", [])
            
            print(f"  Найдено постов: {len(posts)}")
            
            for post in posts:
                p = post.get("data", {})
                title = p.get("title", "")
                post_id = p.get("id", "")
                
                if not title or is_duplicate(f"news_{post_id}"):
                    continue
                
                # Извлекаем картинку
                image = None
                thumb = p.get("thumbnail", "")
                
                if thumb and thumb.startswith("http") and thumb not in ["self", "default", "nsfw"]:
                    image = thumb
                elif p.get("preview"):
                    imgs = p["preview"].get("images", [])
                    if imgs:
                        image = imgs[0].get("source", {}).get("url")
                
                if image:
                    news.append({
                        "title": title,
                        "desc": "",
                        "link": f"https://reddit.com{p.get('permalink', '')}",
                        "source": "Reddit r/games",
                        "image": image
                    })
                    print(f"  ✅ {title[:60]}")
                    
                    if len(news) >= 8:
                        break
            
            SOURCE_STATUS["news"] = "✅"
            print(f"✅ Новости: {len(news)}")
        else:
            print(f"❌ Reddit news: статус {r.status_code}")
            SOURCE_STATUS["news"] = "⚠️"
    
    except Exception as e:
        print(f" Новости: {e}")
        SOURCE_STATUS["news"] = "⚠️"
    
    return news


# === 6. YOUTUBE ===
def get_youtube():
    print("\n🎬 YOUTUBE...")
    videos = []
    
    channels = [
        {"name": "Xbox", "url": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
        {"name": "PlayStation", "url": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
        {"name": "Nintendo", "url": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"}
    ]
    
    try:
        for ch in channels:
            feed = feedparser.parse(ch["url"])
            if feed.entries:
                entry = feed.entries[0]
                videos.append({
                    "title": entry.title.strip(),
                    "link": entry.link,
                    "source": ch["name"]
                })
                print(f"  ✅ {ch['name']}: {entry.title[:50]}")
        
        SOURCE_STATUS["youtube"] = "✅"
    except Exception as e:
        print(f"❌ YouTube: {e}")
        SOURCE_STATUS["youtube"] = "️"
    
    return videos


# === ОТПРАВКА ПОСТОВ ===
def send_post(chat_id, item, post_type="free"):
    emoji = "🎁" if post_type == "free" else "" if post_type == "gp" else ""
    btn = " ЗАБРАТЬ" if post_type == "free" else "📖 GAME PASS" if post_type == "gp" else " КУПИТЬ"
    
    text = f"{emoji} <b>{item['title']}</b>\n\n"
    if item.get("desc"):
        text += f"📝 <i>{item['desc']}</i>\n\n"
    text += f"🖥 <b>Платформа:</b> {item.get('platform', 'PC')}\n\n"
    text += f"<a href='{item['link']}'>{btn}</a>\n"
    
    yt = item["title"].replace(" ", "+")
    text += f"<a href='https://www.youtube.com/results?search_query={yt}'>🎬 Геймплей</a>\n\n"
    
    text += "━━━━━━━━━━━━━━━\n"
    text += "<b>🎮 AlexPlay — твой игровой!</b>\n"
    text += " @AlexPlayDrops — халява\n"
    text += "📰 @AlexPlayHub — новости"
    
    send_to_telegram(chat_id, text, item.get("image"))


# === ПУБЛИКАЦИИ ===
def publish_drops():
    print("\n=== ХАЛЯВА ===")
    epic = get_epic_freebies()
    gp = get_gamerpower_freebies()
    
    all_free = epic + gp
    
    for item in all_free:
        send_post(DROPS_CHANNEL_ID, item, "free")
        time.sleep(2)
    
    if not all_free:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо</b>\n\nМониторим 24/7! 🔔")
    
    print(f"✅ Отправлено: {len(all_free)}")


def publish_hub_gp():
    print("\n=== GAME PASS ===")
    games = get_gamepass()
    
    for item in games:
        send_post(HUB_CHANNEL_ID, item, "gp")
        time.sleep(2)
    
    print(f"✅ Отправлено: {len(games)}")


def publish_hub_deals():
    print("\n=== СКИДКИ ===")
    deals = get_deals()
    
    for item in deals:
        send_post(HUB_CHANNEL_ID, item, "deal")
        time.sleep(2)
    
    print(f"✅ Отправлено: {len(deals)}")


def publish_hub_news():
    print("\n=== НОВОСТИ ===")
    news = get_news()
    
    for item in news:
        text = f"📰 <b>НОВОСТЬ</b>\n\n{item['title']}\n\n"
        text += f" <a href='{item['link']}'>Читать ({item['source']})</a>\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "<b>🎮 AlexPlay — твой игровой!</b>\n"
        text += "💰 @AlexPlayDrops — халява\n"
        text += " @AlexPlayHub — новости"
        
        send_to_telegram(HUB_CHANNEL_ID, text, item.get("image"))
        time.sleep(2)
    
    print(f"✅ Отправлено: {len(news)}")


def publish_hub_video():
    print("\n=== YOUTUBE ===")
    videos = get_youtube()
    
    if videos:
        msg = " <b>ТРЕЙЛЕРЫ</b>\n\n"
        for i, v in enumerate(videos, 1):
            msg += f"{i}. <a href='{v['link']}'>{v['title']}</a> <i>({v['source']})</i>\n\n"
        
        msg += "\n━━━━━━━━━━━━━━━\n"
        msg += "<b> AlexPlay — твой игровой!</b>\n"
        msg += "💰 @AlexPlayDrops — халява\n"
        msg += " @AlexPlayHub — новости"
        
        send_to_telegram(HUB_CHANNEL_ID, msg)
    
    print(f"✅ Отправлено: {len(videos)}")


# === ОТЧЁТ ===
def send_pulse():
    if not CHAT_ID:
        return
    
    msg = f"📊 <b>ОТЧЁТ ALEXPLAY</b>\n"
    msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f" <b>@AlexPlayHub:</b> {get_chat_members(HUB_CHANNEL_ID)}\n"
    msg += f"👥 <b>@AlexPlayDrops:</b> {get_chat_members(DROPS_CHANNEL_ID)}\n\n"
    msg += "🛰 <b>СТАТУС:</b>\n"
    
    for k, v in SOURCE_STATUS.items():
        msg += f"• {k.upper()}: {v}\n"
    
    all_ok = all(v == "✅" for v in SOURCE_STATUS.values())
    msg += f"\n{'✅ Всё работает!' if all_ok else '⚠️ Есть сбои'}"
    
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
        hour = (datetime.now(timezone.utc).hour + 3) % 24
        mode = SCHEDULE.get(hour, "skip")
        print(f"🕐 {hour}:00 МСК → {mode}")
    
    if mode == "skip":
        print("⏭ Пропуск")
        return
    
    print(f" Запуск: {mode}")
    
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
    
    print("✅ Готово!")


if __name__ == "__main__":
    main()
