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
    print("❌ ОШИБКА: Не найдены необходимые секреты!")
    print("Проверь Settings → Secrets and variables → Actions")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

# Cache для предотвращения дублей
SEEN_ITEMS = {}
CACHE_EXPIRY = 86400  # 24 часа

# Расписание
SCHEDULE = {
    9: "drops",        # 12:00 МСК
    12: "hub_news",    # 15:00 МСК
    15: "hub_gp",      # 18:00 МСК
    18: "hub_deals",   # 21:00 МСК
    21: "hub_video"    # 00:00 МСК
}

WARNINGS = []
SOURCE_STATUS = {
    "epic": "—",
    "gamerpower": "—",
    "gamepass": "—",
    "deals": "—",
    "news": "—",
    "youtube": "—"
}


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def is_duplicate(item_id):
    """Проверка на дубликаты (24 часа)"""
    try:
        now = time.time()
        
        # Очистка старых записей
        items_to_remove = []
        for key, timestamp in SEEN_ITEMS.items():
            if now - timestamp > CACHE_EXPIRY:
                items_to_remove.append(key)
        
        for key in items_to_remove:
            del SEEN_ITEMS[key]
        
        # Проверка
        if item_id in SEEN_ITEMS:
            return True
        
        SEEN_ITEMS[item_id] = now
        return False
    except Exception as e:
        print(f"Cache error: {e}")
        return False


def safe_request(url, timeout=20, retries=3):
    """Надёжный HTTP запрос с повторами"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    for attempt in range(retries):
        try:
            print(f"  Запрос к {url[:50]}... (попытка {attempt + 1}/{retries})")
            response = requests.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 200:
                print(f"  ✅ Успешно!")
                return response
            else:
                print(f"  ❌ Статус: {response.status_code}")
                if attempt < retries - 1:
                    time.sleep(3)
        except requests.exceptions.Timeout:
            print(f"  ⏱ Таймаут ({timeout}с)")
            if attempt < retries - 1:
                time.sleep(3)
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Ошибка: {e}")
            if attempt < retries - 1:
                time.sleep(3)
    
    return None


def send_to_telegram(chat_id, text, photo_url=None):
    """Отправка сообщения в Telegram"""
    if not chat_id:
        print("❌ Не указан chat_id")
        return False
    
    try:
        if photo_url and photo_url.startswith("http"):
            # Отправка с фото
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": text[:1000],
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            response = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=25)
        else:
            # Отправка текста
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            response = requests.post(TELEGRAM_URL, data=payload, timeout=15)
        
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False


def get_chat_members(chat_id):
    """Получение количества подписчиков"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount"
        response = requests.get(url, params={"chat_id": chat_id}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("result", "?")
        else:
            return "?"
    except Exception as e:
        print(f"❌ Ошибка получения подписчиков: {e}")
        return "?"


# === 1. EPIC GAMES FREEBIES ===

def get_epic_freebies():
    """Получение бесплатных игр Epic Games Store"""
    print("\n🎁 === EPIC GAMES ===")
    freebies = []
    
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        response = safe_request(url, timeout=25, retries=3)
        
        if response is None:
            print("❌ Epic Games: не удалось получить данные")
            SOURCE_STATUS["epic"] = "⚠️"
            return freebies
        
        # Парсинг JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ Epic Games: ошибка JSON - {e}")
            SOURCE_STATUS["epic"] = "⚠️"
            return freebies
        
        # Извлечение элементов
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        
        if not elements:
            print("⚠️ Epic Games: пустой список игр")
            SOURCE_STATUS["epic"] = "⚠️"
            return freebies
        
        print(f"  Найдено элементов: {len(elements)}")
        
        for element in elements:
            try:
                # Проверка цены
                price_info = element.get("price", {}).get("totalPrice", {})
                discount_price = price_info.get("discountPrice", 999999)
                
                if discount_price == 0:
                    title = element.get("title", "")
                    
                    if title and not is_duplicate(f"epic_{title}"):
                        # Извлечение изображения
                        image_url = None
                        key_images = element.get("keyImages", [])
                        
                        if key_images:
                            for img in key_images:
                                img_type = img.get("type", "")
                                if img_type in ["OfferImageWide", "DieselStoreFrontWide", "Thumbnail"]:
                                    image_url = img.get("url")
                                    break
                        
                        # Описание
                        description = element.get("description", "")
                        if not description:
                            seller = element.get("seller", {}).get("name", "")
                            description = f"Бесплатно в Epic Games Store{(' - ' + seller) if seller else ''}"
                        
                        freebies.append({
                            "platform": "Epic Games",
                            "title": title,
                            "desc": description[:300],
                            "image": image_url,
                            "link": "https://store.epicgames.com/ru/free-games"
                        })
                        
                        print(f"  ✅ Добавлено: {title[:50]}")
            except Exception as e:
                print(f"  ⚠️ Ошибка обработки элемента: {e}")
                continue
        
        SOURCE_STATUS["epic"] = "✅"
        print(f"✅ Epic Games: {len(freebies)} игр")
        
    except Exception as e:
        print(f"❌ Epic Games критическая ошибка: {e}")
        SOURCE_STATUS["epic"] = "⚠️"
    
    return freebies


# === 2. GAMERPOWER FREEBIES ===

def get_gamerpower_freebies():
    """Получение бесплатных игр из GamerPower"""
    print("\n === GAMERPOWER ===")
    freebies = []
    
    try:
        url = "https://www.gamerpower.com/api/giveaways?type=game"
        response = safe_request(url, timeout=20, retries=3)
        
        if response is None:
            print("❌ GamerPower: не удалось получить данные")
            SOURCE_STATUS["gamerpower"] = "⚠️"
            return freebies
        
        # Парсинг JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f" GamerPower: ошибка JSON - {e}")
            SOURCE_STATUS["gamerpower"] = "️"
            return freebies
        
        if not isinstance(data, list):
            print("❌ GamerPower: неожиданный формат данных")
            SOURCE_STATUS["gamerpower"] = "⚠️"
            return freebies
        
        print(f"  Найдено элементов: {len(data)}")
        
        for item in data[:15]:  # Берём первые 15
            try:
                title = item.get("title", "")
                platforms = item.get("platforms", "PC")
                
                if title and not is_duplicate(f"gp_{title}_{platforms}"):
                    # Извлечение данных
                    description = item.get("description", "Бесплатная игра")
                    thumbnail = item.get("thumbnail")
                    giveaway_url = item.get("open_giveaway_url", "")
                    
                    freebies.append({
                        "platform": platforms,
                        "title": title,
                        "desc": description[:300],
                        "image": thumbnail,
                        "link": giveaway_url
                    })
                    
                    print(f"  ✅ Добавлено: {title[:50]} ({platforms})")
            except Exception as e:
                print(f"  ⚠️ Ошибка обработки: {e}")
                continue
        
        SOURCE_STATUS["gamerpower"] = "✅"
        print(f"✅ GamerPower: {len(freebies)} игр")
        
    except Exception as e:
        print(f"❌ GamerPower критическая ошибка: {e}")
        SOURCE_STATUS["gamerpower"] = "⚠️"
    
    return freebies


# === 3. GAME PASS ===

def get_gamepass():
    """Получение новостей о Game Pass"""
    print("\n🎮 === GAME PASS ===")
    games = []
    
    try:
        url = "https://www.reddit.com/r/XboxGamePass/hot.json?limit=20"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = safe_request(url, timeout=20, retries=3)
        
        if response is None:
            print("❌ Game Pass: не удалось получить данные")
            SOURCE_STATUS["gamepass"] = "⚠️"
            return games
        
        # Парсинг JSON
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"❌ Game Pass: ошибка JSON - {e}")
            SOURCE_STATUS["gamepass"] = "⚠️"
            return games
        
        posts = data.get("data", {}).get("children", [])
        
        if not posts:
            print("⚠️ Game Pass: пустой список постов")
            SOURCE_STATUS["gamepass"] = "⚠️"
            return games
        
        print(f"  Найдено постов: {len(posts)}")
        
        for post in posts:
            try:
                post_data = post.get("data", {})
                title = post_data.get("title", "")
                post_id = post_data.get("id", "")
                
                # Фильтр: только новые/добавленные игры
                title_lower = title.lower()
                if any(keyword in title_lower for keyword in ["coming", "new", "added", "arriving", "june", "july", "august"]):
                    
                    if not is_duplicate(f"gp_{post_id}"):
                        # Извлечение изображения
                        image_url = None
                        thumbnail = post_data.get("thumbnail", "")
                        
                        if thumbnail and thumbnail.startswith("http"):
                            image_url = thumbnail
                        else:
                            # Пробуем preview
                            preview = post_data.get("preview", {})
                            if preview:
                                images = preview.get("images", [])
                                if images:
                                    image_url = images[0].get("source", {}).get("url")
                        
                        games.append({
                            "title": title,
                            "desc": "В Xbox Game Pass",
                            "image": image_url,
                            "link": f"https://reddit.com{post_data.get('permalink', '')}"
                        })
                        
                        print(f"  ✅ Добавлено: {title[:50]}")
                        
                        if len(games) >= 5:
                            break
            except Exception as e:
                print(f"  ⚠️ Ошибка обработки поста: {e}")
                continue
        
        SOURCE_STATUS["gamepass"] = "✅"
        print(f"✅ Game Pass: {len(games)} игр")
        
    except Exception as e:
        print(f" Game Pass критическая ошибка: {e}")
        SOURCE_STATUS["gamepass"] = "⚠️"
    
    return games


# === 4. DEALS (СКИДКИ) ===

def get_deals():
    """Получение скидок на игры"""
    print("\n💸 === СКИДКИ ===")
    deals = []
    
    # 1. Steam через CheapShark
    try:
        url = "https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&pageSize=15"
        response = safe_request(url, timeout=20, retries=3)
        
        if response:
            try:
                data = response.json()
                
                for deal in data:
                    try:
                        title = deal.get("title", "")
                        steam_app_id = deal.get("steamAppID", "")
                        savings = float(deal.get("savings", 0))
                        
                        if title and steam_app_id and savings >= 50:
                            link = f"https://store.steampowered.com/app/{steam_app_id}/"
                            
                            if not is_duplicate(f"steam_{steam_app_id}"):
                                normal_price = deal.get("normalPrice", "N/A")
                                
                                deals.append({
                                    "platform": "Steam",
                                    "title": title,
                                    "desc": f"Скидка {int(savings)}% • Обычная цена: ${normal_price}",
                                    "image": None,
                                    "link": link
                                })
                                
                                print(f"  ✅ Steam: {title[:40]} (-{int(savings)}%)")
                    except Exception as e:
                        print(f"  ⚠️ Ошибка обработки Steam deal: {e}")
                        continue
                
                SOURCE_STATUS["deals"] = "✅"
            except json.JSONDecodeError as e:
                print(f"❌ CheapShark: ошибка JSON - {e}")
                SOURCE_STATUS["deals"] = "⚠️"
        else:
            print("❌ CheapShark: не удалось получить данные")
            SOURCE_STATUS["deals"] = "⚠️"
    
    except Exception as e:
        print(f" CheapShark критическая ошибка: {e}")
        SOURCE_STATUS["deals"] = "⚠️"
    
    # 2. Reddit GameDeals
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        queries = [
            ("xbox OR gamepass", "Xbox"),
            ("playstation OR psn", "PlayStation"),
            ("switch", "Nintendo Switch")
        ]
        
        for query, platform in queries:
            try:
                url = f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=5"
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    for post in posts:
                        try:
                            post_data = post.get("data", {})
                            title = post_data.get("title", "")
                            permalink = post_data.get("permalink", "")
                            
                            if "expired" in title.lower() or not permalink:
                                continue
                            
                            # Извлечение процента скидки
                            discount_match = re.search(r'-\s*(\d{1,3})\s*%', title)
                            discount = int(discount_match.group(1)) if discount_match else 50
                            
                            if discount >= 40:
                                link = f"https://reddit.com{permalink}"
                                
                                if not is_duplicate(f"reddit_{permalink}"):
                                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title)
                                    
                                    deals.append({
                                        "platform": platform,
                                        "title": clean_title,
                                        "desc": f"Скидка {discount}%",
                                        "image": None,
                                        "link": link
                                    })
                                    
                                    print(f"  ✅ {platform}: {clean_title[:40]} (-{discount}%)")
                        except Exception as e:
                            print(f"  ⚠️ Ошибка обработки Reddit deal: {e}")
                            continue
            except Exception as e:
                print(f"  ⚠️ Ошибка запроса Reddit {query}: {e}")
                continue
    
    except Exception as e:
        print(f"❌ Reddit GameDeals ошибка: {e}")
    
    # Сортировка: Steam сначала
    deals.sort(key=lambda x: 0 if x["platform"] == "Steam" else 1)
    
    print(f"✅ Всего скидок: {len(deals)}")
    return deals


# === 5. НОВОСТИ ===

def get_news():
    """Получение игровых новостей"""
    print("\n === НОВОСТИ ===")
    news = []
    
    # Reddit r/games
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        url = "https://www.reddit.com/r/games/hot.json?limit=25"
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            print(f"  Найдено постов: {len(posts)}")
            
            for post in posts:
                try:
                    post_data = post.get("data", {})
                    title = post_data.get("title", "")
                    post_id = post_data.get("id", "")
                    
                    if not title or is_duplicate(f"news_{post_id}"):
                        continue
                    
                    # Извлечение изображения
                    image_url = None
                    thumbnail = post_data.get("thumbnail", "")
                    
                    if thumbnail and thumbnail.startswith("http"):
                        image_url = thumbnail
                    else:
                        preview = post_data.get("preview", {})
                        if preview:
                            images = preview.get("images", [])
                            if images:
                                image_url = images[0].get("source", {}).get("url")
                    
                    # Добавляем только если есть картинка
                    if image_url:
                        news.append({
                            "title": title,
                            "desc": "",
                            "link": f"https://reddit.com{post_data.get('permalink', '')}",
                            "source": "Reddit r/games",
                            "image": image_url
                        })
                        
                        print(f"  ✅ Reddit: {title[:50]}")
                        
                        if len(news) >= 8:
                            break
                except Exception as e:
                    print(f"  ⚠️ Ошибка обработки новости: {e}")
                    continue
            
            SOURCE_STATUS["news"] = "✅"
        else:
            print(f"❌ Reddit news: статус {response.status_code}")
            SOURCE_STATUS["news"] = "️"
    
    except Exception as e:
        print(f"❌ Reddit news ошибка: {e}")
        SOURCE_STATUS["news"] = "⚠️"
    
    print(f"✅ Всего новостей: {len(news)}")
    return news


# === 6. YOUTUBE ===

def get_youtube():
    """Получение трейлеров с YouTube"""
    print("\n🎬 === YOUTUBE ===")
    videos = []
    
    channels = [
        {"name": "Xbox", "url": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
        {"name": "PlayStation", "url": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
        {"name": "Nintendo", "url": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"}
    ]
    
    try:
        for channel in channels:
            try:
                feed = feedparser.parse(channel["url"])
                
                if feed.entries:
                    entry = feed.entries[0]
                    videos.append({
                        "title": entry.title.strip(),
                        "link": entry.link,
                        "source": channel["name"]
                    })
                    
                    print(f"  ✅ {channel['name']}: {entry.title[:50]}")
            except Exception as e:
                print(f"  ⚠️ Ошибка {channel['name']}: {e}")
                continue
        
        SOURCE_STATUS["youtube"] = "✅"
        print(f"✅ YouTube: {len(videos)} видео")
    
    except Exception as e:
        print(f" YouTube ошибка: {e}")
        SOURCE_STATUS["youtube"] = "⚠️"
    
    return videos


# === ОТПРАВКА ПОСТОВ ===

def send_post(chat_id, item, post_type="free"):
    """Отправка красивого поста"""
    
    # Определение эмодзи и текста кнопки
    if post_type == "free":
        emoji = ""
        button_text = "🔗 ЗАБРАТЬ БЕСПЛАТНО"
    elif post_type == "gp":
        emoji = "🎮"
        button_text = "📖 В GAME PASS"
    else:
        emoji = "💸"
        button_text = "🛒 КУПИТЬ"
    
    # Формирование текста
    text = f"{emoji} <b>{item['title']}</b>\n\n"
    
    if item.get("desc"):
        text += f" <i>{item['desc']}</i>\n\n"
    
    text += f" <b>Платформа:</b> {item.get('platform', 'PC')}\n\n"
    text += f"<a href='{item['link']}'>{button_text}</a>\n"
    
    # Кнопка YouTube
    youtube_query = item["title"].replace(" ", "+")
    text += f"<a href='https://www.youtube.com/results?search_query={youtube_query}'>🎬 Геймплей</a>\n\n"
    
    # Реклама каналов
    text += "━━━━━━━━━━━━━━━\n"
    text += "<b>🎮 AlexPlay — твой игровой помощник!</b>\n"
    text += "💰 @AlexPlayDrops — халява и скидки\n"
    text += "📰 @AlexPlayHub — новости и обзоры"
    
    # Отправка
    send_to_telegram(chat_id, text, item.get("image"))


# === ПУБЛИКАЦИИ ===

def publish_drops():
    """Публикация халявы"""
    print("\n=== ПУБЛИКАЦИЯ ХАЛЯВЫ ===")
    
    epic_games = get_epic_freebies()
    gamerpower_games = get_gamerpower_freebies()
    
    all_freebies = epic_games + gamerpower_games
    
    print(f"\n📤 Отправка {len(all_freebies)} постов...")
    
    for item in all_freebies:
        send_post(DROPS_CHANNEL_ID, item, "free")
        time.sleep(2)  # Пауза чтобы не спамить
    
    if not all_freebies:
        send_to_telegram(
            DROPS_CHANNEL_ID,
            "🤖 <b>Пока тихо</b>\n\n"
            "Крупных раздач сейчас нет, но мы мониторим 24/7! 🔔\n\n"
            "━━━━━━━━━━━━━━━\n"
            "<b>🎮 AlexPlay — твой игровой помощник!</b>\n"
            "💰 @AlexPlayDrops — халява и скидки\n"
            "📰 @AlexPlayHub — новости и обзоры"
        )
    
    print(f"✅ Drops опубликован: {len(all_freebies)} постов")


def publish_hub_gp():
    """Публикация Game Pass"""
    print("\n=== ПУБЛИКАЦИЯ GAME PASS ===")
    
    games = get_gamepass()
    
    print(f"\n📤 Отправка {len(games)} постов...")
    
    for item in games:
        send_post(HUB_CHANNEL_ID, item, "gp")
        time.sleep(2)
    
    print(f"✅ Game Pass опубликован: {len(games)} постов")


def publish_hub_deals():
    """Публикация скидок"""
    print("\n=== ПУБЛИКАЦИЯ СКИДОК ===")
    
    deals = get_deals()
    
    print(f"\n📤 Отправка {len(deals)} постов...")
    
    for item in deals:
        send_post(HUB_CHANNEL_ID, item, "deal")
        time.sleep(2)
    
    print(f"✅ Deals опубликован: {len(deals)} постов")


def publish_hub_news():
    """Публикация новостей"""
    print("\n=== ПУБЛИКАЦИЯ НОВОСТЕЙ ===")
    
    news_items = get_news()
    
    print(f"\n📤 Отправка {len(news_items)} постов...")
    
    for item in news_items:
        text = f"📰 <b>НОВОСТЬ</b>\n\n{item['title']}\n\n"
        text += f"🔗 <a href='{item['link']}'>Читать ({item['source']})</a>\n\n"
        text += "━━━━━━━━━━━━━━━\n"
        text += "<b> AlexPlay — твой игровой помощник!</b>\n"
        text += "💰 @AlexPlayDrops — халява и скидки\n"
        text += "📰 @AlexPlayHub — новости и обзоры"
        
        send_to_telegram(HUB_CHANNEL_ID, text, item.get("image"))
        time.sleep(2)
    
    print(f"✅ News опубликован: {len(news_items)} постов")


def publish_hub_video():
    """Публикация YouTube трейлеров"""
    print("\n=== ПУБЛИКАЦИЯ YOUTUBE ===")
    
    videos = get_youtube()
    
    if videos:
        msg = "🎬 <b>СВЕЖИЕ ТРЕЙЛЕРЫ</b>\n\n"
        
        for i, video in enumerate(videos, 1):
            msg += f"{i}. <a href='{video['link']}'>{video['title']}</a> <i>({video['source']})</i>\n\n"
        
        msg += "\n━━━━━━━━━━━━━━━\n"
        msg += "<b>🎮 AlexPlay — твой игровой помощник!</b>\n"
        msg += " @AlexPlayDrops — халява и скидки\n"
        msg += "📰 @AlexPlayHub — новости и обзоры"
        
        send_to_telegram(HUB_CHANNEL_ID, msg)
        print(f"✅ Video опубликован: {len(videos)} постов")
    else:
        print("⚠️ Нет видео для публикации")


# === ОТЧЁТЫ ===

def send_pulse():
    """Отправка отчёта"""
    if not CHAT_ID:
        return
    
    msg = f"📊 <b>ОТЧЁТ ALEXPLAY</b>\n"
    msg += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    msg += f" <b>@AlexPlayHub:</b> {get_chat_members(HUB_CHANNEL_ID)}\n"
    msg += f"👥 <b>@AlexPlayDrops:</b> {get_chat_members(DROPS_CHANNEL_ID)}\n\n"
    msg += "🛰 <b>СТАТУС ИСТОЧНИКОВ:</b>\n"
    
    for key, label in [
        ("epic", "Epic Games"),
        ("gamerpower", "GamerPower"),
        ("gamepass", "Game Pass"),
        ("deals", "Скидки"),
        ("news", "Новости"),
        ("youtube", "YouTube")
    ]:
        status = SOURCE_STATUS.get(key, "—")
        msg += f"• {label}: {status}\n"
    
    all_ok = all(SOURCE_STATUS.get(k) == "✅" for k in SOURCE_STATUS)
    msg += f"\n{'✅ Всё работает!' if all_ok else '⚠️ Есть сбои (см. алерты)'}"
    
    send_to_telegram(CHAT_ID, msg)


def send_alert():
    """Отправка алертов об ошибках"""
    if not CHAT_ID or not WARNINGS:
        return
    
    msg = "🚨 <b>СБОИ В БОТЕ</b>\n\n"
    for warning in WARNINGS:
        msg += f"⚠️ {warning}\n"
    
    send_to_telegram(CHAT_ID, msg[:4000])


def run_safe(name, func):
    """Безопасный запуск функции"""
    try:
        print(f"\n🚀 Запуск {name}...")
        func()
    except Exception as e:
        error_msg = f"{name}: {str(e)}"
        WARNINGS.append(error_msg)
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()


# === ГЛАВНАЯ ФУНКЦИЯ ===

def main():
    """Главная функция"""
    print("=" * 50)
    print("🎮 ALEXPLAY BOT ЗАПУСК")
    print("=" * 50)
    
    # Определение режима
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "auto"
    
    if mode == "auto":
        moscow_hour = (datetime.now(timezone.utc).hour + 3) % 24
        mode = SCHEDULE.get(moscow_hour, "skip")
        print(f" Время: {moscow_hour}:00 МСК → Режим: {mode}")
    
    if mode == "skip":
        print("⏭ Пропуск (не время публикации)")
        return
    
    print(f"🎯 Режим: {mode}")
    print("=" * 50)
    
    # Запуск задач
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
    
    # Отправка алертов если есть ошибки
    if WARNINGS:
        print(f"\n⚠️ Найдено ошибок: {len(WARNINGS)}")
        send_alert()
    
    # Отправка отчёта
    if mode in ("hub_video", "all"):
        print("\n📊 Отправка отчёта...")
        send_pulse()
    
    print("\n" + "=" * 50)
    print("✅ ГОТОВО!")
    print("=" * 50)


if __name__ == "__main__":
    main()
