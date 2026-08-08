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

if not all([BOT_TOKEN, DROPS_CHANNEL_ID, HUB_CHANNEL_ID]):
    print("ОШИБКА: Не найдены необходимые секреты!")
    exit(1)

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_PHOTO_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

SCHEDULE = {9: "drops", 12: "hub_game", 15: "hub_news", 18: "hub_steam", 21: "hub_video"}
WARNINGS = []
SOURCE_STATUS = {"epic": "—", "deals": "—", "game_db": "—", "rss": "—", "youtube": "—"}

# === ВНУТРЕННЯЯ БАЗА ИГР (60 игр, работает всегда, без API) ===
GAME_DATABASE = [
    {"title": "The Witcher 3: Wild Hunt", "year": "2015", "dev": "CD Projekt RED", "desc": "Эпичная RPG про Геральта из Ривии. Один из лучших сюжетов в истории игр.", "fact": "На создание игры ушло 3.5 года и 81 миллион долларов. Это больше, чем бюджет многих голливудских блокбастеров.", "genres": ["RPG", "Приключение"]},
    {"title": "Elden Ring", "year": "2022", "dev": "FromSoftware", "desc": "Мрачное фэнтези в открытом мире от создателей Dark Souls.", "fact": "Мир игры создавался совместно с Джорджем Мартином, автором 'Игры престолов'. Он написал мифологию мира.", "genres": ["RPG", "Экшен"]},
    {"title": "Baldur's Gate 3", "year": "2023", "dev": "Larian Studios", "desc": "Эталон современных CRPG с невероятной свободой выбора.", "fact": "Разработка заняла 6 лет. В игре более 170 часов озвученных диалогов.", "genres": ["RPG", "Стратегия"]},
    {"title": "Red Dead Redemption 2", "year": "2018", "dev": "Rockstar Games", "desc": "Самый живой открытый мир и история о Диком Западе.", "fact": "На разработку ушло 8 лет и более 2000 человек. Бюджет превысил 500 миллионов долларов.", "genres": ["Экшен", "Приключение"]},
    {"title": "God of War (2018)", "year": "2018", "dev": "Santa Monica Studio", "desc": "Эпичные сражения с богами и трогательная история отца и сына.", "fact": "Игра получила 'Игру года' на The Game Awards 2018, обойдя Red Dead Redemption 2.", "genres": ["Экшен", "Приключение"]},
    {"title": "Hollow Knight", "year": "2017", "dev": "Team Cherry", "desc": "Шедевр метроидвании в красивом рисованном стиле.", "fact": "Игру создали всего 3 человека. Изначально это был проект на Kickstarter с целью в 35 тысяч долларов.", "genres": ["Приключение", "Инди"]},
    {"title": "Hades", "year": "2020", "dev": "Supergiant Games", "desc": "Рогалик о побеге из преисподней с божественным стилем.", "fact": "Первый рогалик, получивший премию Хьюго за лучшее литературное произведение.", "genres": ["Экшен", "Инди"]},
    {"title": "Celeste", "year": "2018", "dev": "Maddy Makes Games", "desc": "Сложный и трогательный платформер о преодолении себя.", "fact": "Главная героиня страдает тревожностью, и это отразило личный опыт разработчика.", "genres": ["Платформер", "Инди"]},
    {"title": "Stardew Valley", "year": "2016", "dev": "ConcernedApe", "desc": "Уютный симулятор фермы, созданный одним человеком.", "fact": "Эрик Барон создал игру в одиночку за 4.5 года: программировал, рисовал, писал музыку и сценарий.", "genres": ["Симулятор", "Инди"]},
    {"title": "Portal 2", "year": "2011", "dev": "Valve", "desc": "Гениальные головоломки с порталами и блестящий юмор.", "fact": "Кооперативный режим был добавлен после того, как разработчики увидели, как игроки пытаются пройти игру вдвоём.", "genres": ["Головоломка", "Шутер"]},
    {"title": "Half-Life 2", "year": "2004", "dev": "Valve", "desc": "Легендарный шутер, изменивший индустрию навсегда.", "fact": "Игра разрабатывалась 5 лет и стоила 40 миллионов долларов. Она впервые использовала физический движок Havok.", "genres": ["Шутер", "Приключение"]},
    {"title": "Dark Souls", "year": "2011", "dev": "FromSoftware", "desc": "Игра, давшая имя целому жанру. Prepare to die.", "fact": "Изначально игра называлась 'Dark Ring', но название пришлось изменить из-за британского сленгового выражения.", "genres": ["RPG", "Экшен"]},
    {"title": "Mass Effect 2", "year": "2010", "dev": "BioWare", "desc": "Космическая опера, где решения действительно имеют значение.", "fact": "Финальная миссия 'Suicide Mission' считается одной из лучших в истории RPG. Ваши решения ведут к гибели членов команды.", "genres": ["RPG", "Шутер"]},
    {"title": "BioShock", "year": "2007", "dev": "Irrational Games", "desc": "Философский шутер в подводном городе Восторг.", "fact": "Название города Rapture отсылает к философии объективизма Айн Рэнд.", "genres": ["Шутер", "Приключение"]},
    {"title": "Disco Elysium", "year": "2019", "dev": "ZA/UM", "desc": "RPG без боёв, где сражаются диалогами.", "fact": "В игре более миллиона слов текста — это больше, чем во 'Властелине колец' в 3 раза.", "genres": ["RPG", "Приключение"]},
    {"title": "DOOM Eternal", "year": "2020", "dev": "id Software", "desc": "Балет насилия под тяжёлый метал.", "fact": "Саундтрек Мика Гордона настолько тяжёлый, что некоторые фанаты использовали его для тренировок.", "genres": ["Шутер", "Экшен"]},
    {"title": "Cuphead", "year": "2017", "dev": "StudioMDHR", "desc": "Беги и стреляй в стиле мультфильмов 1930-х.", "fact": "Вся анимация рисовалась вручную на бумаге. Разработчики заложили дом, чтобы закончить игру.", "genres": ["Экшен", "Инди"]},
    {"title": "Undertale", "year": "2015", "dev": "Toby Fox", "desc": "RPG, где можно никого не убивать.", "fact": "Тоби Фокс создал игру в одиночку за 2.7 года. Изначально это был фан-проект по EarthBound.", "genres": ["RPG", "Инди"]},
    {"title": "Terraria", "year": "2011", "dev": "Re-Logic", "desc": "2D-песочница с огромной глубиной и боссами.", "fact": "Игра получает бесплатные обновления уже более 12 лет. Последнее крупное обновление вышло в 2020 году.", "genres": ["Песочница", "Приключение"]},
    {"title": "Minecraft", "year": "2011", "dev": "Mojang", "desc": "Самая продаваемая игра в истории.", "fact": "Microsoft купила Mojang за 2.5 миллиарда долларов в 2014 году. На тот момент это была самая дорогая сделка в истории игр.", "genres": ["Песочница", "Приключение"]},
    {"title": "Cyberpunk 2077", "year": "2020", "dev": "CD Projekt RED", "desc": "RPG в мегаполисе будущего.", "fact": "После катастрофического запуска игра была переделана за 3 года. Сейчас это одна из самых популярных RPG на Steam.", "genres": ["RPG", "Экшен"]},
    {"title": "Sekiro: Shadows Die Twice", "year": "2019", "dev": "FromSoftware", "desc": "Отточенный бой на клинках в Японии эпохи сэгоку.", "fact": "Игра получила 'Игру года' на The Game Awards 2019, обойдя Death Stranding и Resident Evil 2.", "genres": ["Экшен", "Приключение"]},
    {"title": "Outer Wilds", "year": "2019", "dev": "Mobius Digital", "desc": "Космическое приключение с петлёй времени.", "fact": "Изначально это был студенческий проект в Университете Южной Калифорнии.", "genres": ["Приключение", "Головоломка"]},
    {"title": "Slay the Spire", "year": "2019", "dev": "MegaCrit", "desc": "Карточный рогалик, установивший стандарт жанра.", "fact": "Разработчики добавили более 100 обновлений после релиза, расширив игру в разы.", "genres": ["Стратегия", "Инди"]},
    {"title": "Resident Evil 4", "year": "2005", "dev": "Capcom", "desc": "Революция в жанре survival horror.", "fact": "Игру переделывали 4 раза в процессе разработки. Оригинальная версия почти полностью отличалась от финальной.", "genres": ["Хоррор", "Экшен"]},
    {"title": "The Last of Us", "year": "2013", "dev": "Naughty Dog", "desc": "История выживания в постапокалиптическом мире.", "fact": "На основе игры снят сериал HBO, который получил множество наград и стал культурным феноменом.", "genres": ["Экшен", "Приключение"]},
    {"title": "Skyrim", "year": "2011", "dev": "Bethesda", "desc": "Легендарная RPG с огромным открытым миром.", "fact": "Игра переиздавалась на всех возможных платформах: PC, консоли, VR, Amazon Alexa и даже Samsung Smart Fridge.", "genres": ["RPG", "Приключение"]},
    {"title": "Fallout: New Vegas", "year": "2010", "dev": "Obsidian", "desc": "Лучшая RPG во вселенной Fallout.", "fact": "Игру разработали всего за 18 месяцев, взяв за основу движок Fallout 3.", "genres": ["RPG", "Шутер"]},
    {"title": "Bloodborne", "year": "2015", "dev": "FromSoftware", "desc": "Готический хоррор от создателей Dark Souls.", "fact": "Игра разработана эксклюзивно для PlayStation 4. Фанаты уже 9 лет просят PC-порт.", "genres": ["RPG", "Экшен"]},
    {"title": "Persona 5", "year": "2016", "dev": "Atlus", "desc": "Стильная JRPG о старшеклассниках-фантомах.", "fact": "В игре более 100 часов контента, и это без учёта побочной версии Persona 5 Royal.", "genres": ["RPG", "Приключение"]},
    {"title": "GTA V", "year": "2013", "dev": "Rockstar Games", "desc": "Феномен поп-культуры с тремя героями.", "fact": "Игра заработала 1 миллиард долларов за первые 3 дня. Это быстрее, чем любой фильм в истории.", "genres": ["Экшен", "Приключение"]},
    {"title": "Super Mario Odyssey", "year": "2017", "dev": "Nintendo", "desc": "Квинтэссенция 3D-платформинга.", "fact": "Механика 'Кэппи' (шляпы, в которую можно вселяться) изначально была побочной идеей, которая стала основой игры.", "genres": ["Платформер", "Приключение"]},
    {"title": "Zelda: Breath of the Wild", "year": "2017", "dev": "Nintendo", "desc": "Революция в жанре открытых миров.", "fact": "Игра получила 10/10 от большинства изданий и считается одной из лучших игр всех времён.", "genres": ["Приключение", "RPG"]},
    {"title": "Return of the Obra Dinn", "year": "2018", "dev": "Lucas Pope", "desc": "Детектив на корабле-призраке.", "fact": "Игра создана одним человеком. Уникальный графический стиль имитирует старые Macintosh компьютеры.", "genres": ["Головоломка", "Приключение"]},
    {"title": "Vampire Survivors", "year": "2022", "dev": "poncle", "desc": "Игра, породившая жанр 'bullet heaven'.", "fact": "Игру создал один разработчик за несколько месяцев. Цена в раннем доступе была всего 2.99$.", "genres": ["Экшен", "Инди"]},
    {"title": "Death Stranding", "year": "2019", "dev": "Kojima Productions", "desc": "Философская игра о доставке и связях между людьми.", "fact": "Хидео Кодзима создал игру после ухода из Konami. В главных ролях снялись Мадс Миккельсен и Норман Ридус.", "genres": ["Экшен", "Приключение"]},
    {"title": "It Takes Two", "year": "2021", "dev": "Hazelight", "desc": "Кооперативное приключение для двоих.", "fact": "Игра получила 'Игру года' на The Game Awards 2021. Поиграть можно только вдвоём, одиночный режим отсутствует.", "genres": ["Приключение", "Платформер"]},
    {"title": "Horizon Zero Dawn", "year": "2017", "dev": "Guerrilla Games", "desc": "Постапокалипсис с роботами-динозаврами.", "fact": "Студия ранее делала только шутеры (Killzone). Horizon стал их первой RPG и первой игрой не-шутером.", "genres": ["Экшен", "RPG"]},
    {"title": "Monster Hunter: World", "year": "2018", "dev": "Capcom", "desc": "Охота на гигантских монстров с друзьями.", "fact": "Игра стала самой продаваемой в истории Capcom — более 20 миллионов копий.", "genres": ["Экшен", "RPG"]},
    {"title": "Control", "year": "2019", "dev": "Remedy", "desc": "Сюрреалистичный экшен в паранормальном здании.", "fact": "Действие игры происходит в той же вселенной, что и Alan Wake. Между играми десятки скрытых связей.", "genres": ["Экшен", "Приключение"]},
    {"title": "Alan Wake 2", "year": "2023", "dev": "Remedy", "desc": "Сюрреалистический хоррор, стирающий границы реальности.", "fact": "Игра вышла через 13 лет после первой части. Разработка заняла более 5 лет.", "genres": ["Хоррор", "Приключение"]},
    {"title": "Dishonored", "year": "2012", "dev": "Arkane Studios", "desc": "Стелс-экшен в мире стимпанка.", "fact": "Игру можно пройти, не убив ни одного человека. За это дают специальное достижение 'Clean Hands'.", "genres": ["Экшен", "Приключение"]},
    {"title": "Prey (2017)", "year": "2017", "dev": "Arkane Studios", "desc": "Научно-фантастический триллер на космической станции.", "fact": "Игра имеет один из лучших сюжетных твистов в истории игр. Начало игры полностью меняет восприятие происходящего.", "genres": ["Шутер", "RPG"]},
    {"title": "Titanfall 2", "year": "2016", "dev": "Respawn", "desc": "Лучший шутер с мехами и одиночной кампанией.", "fact": "Кампания игры считается одной из лучших в истории шутеров от первого лица.", "genres": ["Шутер", "Экшен"]},
    {"title": "Subnautica", "year": "2018", "dev": "Unknown Worlds", "desc": "Выживание на инопланетной подводной планете.", "fact": "Игра изначально была проектом на Unity для геймджема. Разработчики расширили её до полноценной игры.", "genres": ["Приключение", "Симулятор"]},
    {"title": "Sifu", "year": "2022", "dev": "Sloclap", "desc": "Хардкорный beat'em'up о мести и старении.", "fact": "Уникальная механика: каждый раз, когда умираете, персонаж стареет. Пройти игру можно только молодым.", "genres": ["Экшен", "Инди"]},
    {"title": "Inside", "year": "2016", "dev": "Playdead", "desc": "Мрачный платформер с глубоким смыслом.", "fact": "Игра не содержит ни одного слова текста или диалогов. Вся история рассказана через визуал.", "genres": ["Платформер", "Инди"]},
    {"title": "Limbo", "year": "2010", "dev": "Playdead", "desc": "Атмосферный платформер в чёрно-белом стиле.", "fact": "Первая игра студии. Создана всего 8 людьми.", "genres": ["Платформер", "Инди"]},
    {"title": "Ori and the Blind Forest", "year": "2015", "dev": "Moon Studios", "desc": "Красивейший метроидвания-платформер.", "fact": "Разработчики работали из разных стран мира удалённо. Студия никогда не собиралась в одном офисе.", "genres": ["Платформер", "Приключение"]},
    {"title": "Gris", "year": "2018", "dev": "Nomada Studio", "desc": "Платформер-картина о потере и надежде.", "fact": "Игра создана бывшим художником Ubisoft. Каждый кадр можно повесить как картину.", "genres": ["Платформер", "Инди"]},
    {"title": "Journey", "year": "2012", "dev": "thatgamecompany", "desc": "Медитативное приключение в пустыне.", "fact": "Первая видеоигра, номинированная на премию Грэмми за саундтрек.", "genres": ["Приключение", "Инди"]},
    {"title": "What Remains of Edith Finch", "year": "2017", "dev": "Giant Sparrow", "desc": "Антология историй проклятой семьи.", "fact": "Игра получила BAFTA как лучшая игра 2017 года, обойдя Zelda и Mario Odyssey.", "genres": ["Приключение", "Инди"]},
    {"title": "Firewatch", "year": "2016", "dev": "Campo Santo", "desc": "Детектив в глуши леса.", "fact": "В игре всего два персонажа, и один из них слышен только по рации. Весь сюжет построен на диалогах.", "genres": ["Приключение", "Инди"]},
    {"title": "Dead Cells", "year": "2018", "dev": "Motion Twin", "desc": "Динамичный roguevania с потрясающим боем.", "fact": "Игру создала кооперативная студия, где все разработчики имеют равные доли в прибыли.", "genres": ["Экшен", "Инди"]},
    {"title": "Shovel Knight", "year": "2014", "dev": "Yacht Club Games", "desc": "Любовное письмо эпохе NES.", "fact": "Изначально это был Kickstarter-проект с целью 75 тысяч долларов. Собрали более 300 тысяч.", "genres": ["Платформер", "Инди"]},
    {"title": "Hotline Miami", "year": "2012", "dev": "Dennaton Games", "desc": "Безумный топ-даун шутер под синтвейв.", "fact": "Игра создана двумя людьми. Саундтрек стал культовым и породил волну популярности synthwave-музыки.", "genres": ["Экшен", "Инди"]},
    {"title": "Katana ZERO", "year": "2019", "dev": "Askiisoft", "desc": "Неоновый слэшер с механикой замедления времени.", "fact": "Разработчик работал над игрой 4 года в одиночку, параллельно работая на другой работе.", "genres": ["Экшен", "Инди"]},
    {"title": "Pizza Tower", "year": "2023", "dev": "Tour De Pizza", "desc": "Безумный платформер в стиле Wario Land.", "fact": "Игра разрабатывалась 6 лет. Создана командой из 3 человек.", "genres": ["Платформер", "Инди"]},
    {"title": "Balatro", "year": "2024", "dev": "LocalThunk", "desc": "Покерный рогалик, взорвавший чарты.", "fact": "Создан одним разработчиком. Продал более 1 миллиона копий за первый месяц.", "genres": ["Стратегия", "Инди"]},
    {"title": "Helldivers 2", "year": "2024", "dev": "Arrowhead", "desc": "Кооперативный шутер про демократию.", "fact": "Игра стала самой продаваемой в истории PlayStation на PC. Более 12 миллионов копий за первые 3 месяца.", "genres": ["Шутер", "Экшен"]},
    {"title": "Palworld", "year": "2024", "dev": "Pocketpair", "desc": "Покемоны с пистолетами и выживанием.", "fact": "За первые 3 дня игра продалась тиражом 6 миллионов копий, став самой быстрорастущей игрой в Steam.", "genres": ["Приключение", "Симулятор"]},
    {"title": "Lethal Company", "year": "2023", "dev": "Zeekerss", "desc": "Кооперативный хоррор о сборе лута.", "fact": "Игру создал один разработчик в Roblox-студии. Стала вирусным хитом благодаря стримерам.", "genres": ["Хоррор", "Инди"]},
    {"title": "Content Warning", "year": "2024", "dev": "SkullCrusher Games", "desc": "Кооперативный хоррор про съёмку страшного контента.", "fact": "За первые 2 недели игра набрала более 200 000 положительных отзывов в Steam.", "genres": ["Хоррор", "Инди"]},
    {"title": "Black Myth: Wukong", "year": "2024", "dev": "Game Science", "desc": "Визуально потрясающий экшен по мотивам китайской мифологии.", "fact": "Игра стала самой быстрорастущей одиночной игрой в истории — 2.2 миллиона одновременных игроков в Steam.", "genres": ["Экшен", "RPG"]},
    {"title": "Animal Well", "year": "2024", "dev": "Billy Basso", "desc": "Атмосферная метроидвания с уникальным визуалом.", "fact": "Игру создал один разработчик за 7 лет. В ней спрятаны сотни секретов, которые сообщество до сих пор разгадывает.", "genres": ["Приключение", "Инди"]},
    {"title": "Dredge", "year": "2023", "dev": "Black Salt Games", "desc": "Рыбалка с элементами лавкрафтовского хоррора.", "fact": "Небольшая инди-студия из 3 человек создала одну из самых атмосферных игр года.", "genres": ["Приключение", "Хоррор"]},
]

GENRE_TAG_MAP = {"Экшен": "Action", "RPG": "RPG", "Приключение": "Adventure", "Стратегия": "Strategy", "Шутер": "Shooter", "Симулятор": "Simulation", "Головоломка": "Puzzle", "Платформер": "Platformer", "Инди": "Indie", "Хоррор": "Horror", "Гонки": "Racing", "Песочница": "Sandbox"}
RSS_SOURCES = [
    {"name": "DTF", "url": "https://dtf.ru/rss", "lang": "ru"},
    {"name": "StopGame", "url": "https://stopgame.ru/rss/news", "lang": "ru"},
]
YOUTUBE_CHANNELS = [
    {"name": "Nintendo", "feed": "https://www.youtube.com/feeds/videos.xml?user=Nintendo"},
    {"name": "PlayStation", "feed": "https://www.youtube.com/feeds/videos.xml?user=PlayStation"},
    {"name": "Xbox", "feed": "https://www.youtube.com/feeds/videos.xml?user=xbox"},
]

def fetch_json(url, headers=None, timeout=15, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except:
            if attempt == retries - 1:
                return None
            time.sleep(2)

def send_to_telegram(chat_id, text):
    if not chat_id: return False
    try:
        r = requests.post(TELEGRAM_URL, data={"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
        return r.status_code == 200
    except:
        return False

def send_photo_to_telegram(chat_id, photo_url, caption, reply_markup=None):
    if not photo_url: return send_to_telegram(chat_id, caption)
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption[:1000], "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(TELEGRAM_PHOTO_URL, data=payload, timeout=15)
        return r.status_code == 200 or send_to_telegram(chat_id, caption)
    except:
        return send_to_telegram(chat_id, caption)

def get_chat_members(chat_id):
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount", params={"chat_id": chat_id}, timeout=10)
        return r.json().get("result", "?") if r.status_code == 200 else "?"
    except: return "?"

def fmt_num(n): return f"{int(n):,}".replace(",", " ") if n else "0"
def make_hashtags(genres): 
    tags = [GENRE_TAG_MAP.get(g) for g in genres if GENRE_TAG_MAP.get(g)]
    tags = list(dict.fromkeys(tags))[:3] + ["ИграДня", "AlexPlay"]
    return " ".join("#" + t for t in tags)

def build_inline_buttons(slug, trailer_url, title):
    rows = [[{"text": "🎁 Забрать халяву", "url": "https://t.me/AlexPlayDrops"}]]
    if trailer_url:
        rows.append([{"text": "🎬 Трейлер", "url": trailer_url}])
    else:
        rows.append([{"text": "🎬 Обзоры на YouTube", "url": f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+обзор"}])
    return {"inline_keyboard": rows}

# === ИГРА ДНЯ (внутренняя база, работает всегда) ===
def get_game_of_day():
    print("Выбираем игру дня из внутренней базы...")
    day = datetime.now().timetuple().tm_yday
    game = GAME_DATABASE[day % len(GAME_DATABASE)]
    SOURCE_STATUS["game_db"] = "✅"
    
    trailer = ""
    try:
        videos = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id=UC-lHJZR3Gqxm24_Vd_AJ5Yw").entries
        # Запасной трейлер из поиска
        trailer = f"https://www.youtube.com/results?search_query={game['title'].replace(' ', '+')}+trailer"
    except:
        trailer = f"https://www.youtube.com/results?search_query={game['title'].replace(' ', '+')}+trailer"
    
    return {
        "title": game["title"], "year": game["year"], "rating": "—",
        "metacritic": None, "playtime": None, "added": None,
        "dev": game["dev"], "genres_str": ", ".join(game["genres"]),
        "genres_list": game["genres"], "desc": game["desc"],
        "fact": game["fact"], "image": None, "slug": "",
        "trailer": trailer
    }

def build_game_caption(d):
    msg = f"👾 <b>ИГРА ДНЯ</b>\n\n🎮 <b>{d['title']}</b> <i>({d['year']})</i>\n"
    msg += f"🏢 <i>{d['dev']}</i>\n\n"
    msg += f"📝 <i>{d['desc']}</i>\n\n📊 <b>ПАСПОРТ ИГРЫ</b>\n"
    if d['genres_str']: msg += f"🎭 Жанры: {d['genres_str']}\n"
    msg += "\n" + make_hashtags(d['genres_list'])
    return msg

def build_fact(d):
    return f"💡 <b>ФАКТ ДНЯ</b>\n\n🎮 <b>{d['title']}</b>\n\n{d.get('fact', '')}\n\n💬 <i>Играл? Поделись впечатлениями в комментариях!</i>"

# === ХАЛЯВА: Epic + ВСЕ бесплатные игры Steam (усиленный поиск) ===
def get_freebies():
    print("Сбор всех бесплатных игр...")
    freebies = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # Epic Games
    try:
        data = fetch_json("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions", headers, timeout=15)
        if data:
            elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []) or []
            for el in elements:
                if el.get("price", {}).get("totalPrice", {}).get("discountPrice", 999999) == 0:
                    freebies.append({"title": f"🟣 [EPIC] {el.get('title')} (забрать навсегда)", "link": "https://store.epicgames.com/ru/free-games", "discount": 100})
            SOURCE_STATUS["epic"] = "✅" if freebies else "⚠️"
    except:
        SOURCE_STATUS["epic"] = "⚠️"

    # УСИЛЕННЫЙ ПОИСК бесплатных игр на Reddit
    subreddits = ["FreeGameFindings", "FreeGamesOnSteam", "GameDealsFree"]
    keywords = r'\b(free|100%|giveaway|free to keep|free steam key|раздача|навсегда|бесплатно)\b'
    
    for sub in subreddits:
        try:
            data = fetch_json(f"https://www.reddit.com/r/{sub}/hot.json?limit=20", headers, timeout=10)
            if not data: continue
            for post in data.get("data", {}).get("children", []):
                p = post["data"]
                title = p.get("title", "")
                low = title.lower()
                
                if re.search(keywords, title, re.IGNORECASE) and "expired" not in low and "ended" not in low:
                    platform = "🟢"
                    if "steam" in low: platform = "💻 [STEAM]"
                    elif "epic" in low: platform = "🟣 [EPIC]"
                    elif "gog" in low: platform = "💽 [GOG]"
                    elif "xbox" in low or "game pass" in low: platform = "🟩 [XBOX]"
                    elif "psn" in low or "playstation" in low: platform = "🟦 [PS]"
                    elif "switch" in low: platform = "🟥 [SWITCH]"
                    elif "android" in low: platform = "📱 [ANDROID]"
                    elif "ios" in low: platform = "📱 [iOS]"
                    
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title).strip()
                    link = "https://reddit.com" + p["permalink"]
                    
                    if not any(f['link'] == link for f in freebies):
                        freebies.append({
                            "title": f"{platform} {clean_title}",
                            "link": link,
                            "discount": 100
                        })
        except Exception as e:
            print(f"Reddit {sub} сбой: {e}")

    return freebies[:8]

# === СКИДКИ (CheapShark + Reddit) ===
def get_deals():
    print("Сбор скидок...")
    deals = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # CheapShark (Steam скидки)
    try:
        cs = fetch_json("https://www.cheapshark.com/api/1.0/deals?storeID=1&discount=50&upperPrice=30&pageSize=20", headers, timeout=10)
        if cs:
            for d in cs:
                savings = int(float(d.get("savings", 0)))
                if savings >= 50 and d.get("title"):
                    steam_id = d.get("steamAppID", "")
                    link = f"https://store.steampowered.com/app/{steam_id}/" if steam_id else "https://store.steampowered.com/"
                    deals.append({
                        "title": f"💻 [STEAM] −{savings}% | {d['title']}",
                        "link": link,
                        "discount": savings
                    })
    except Exception as e:
        print(f"CheapShark сбой: {e}")

    # Reddit консоли + Game Pass
    queries = [
        ("xbox OR gamepass", "🟩"),
        ("psn OR playstation", "🟦"),
        ("switch OR nintendo", "🟥"),
    ]
    
    for query, emoji in queries:
        try:
            data = fetch_json(f"https://www.reddit.com/r/GameDeals/search.json?q={query}&restrict_sr=1&sort=new&t=week&limit=15", headers, timeout=10)
            if not data: continue
            for post in data.get("data", {}).get("children", []):
                p = post["data"]
                title = p["title"]
                low = title.lower()
                
                if "expired" in low or "ended" in low:
                    continue
                
                discount = 0
                m = re.search(r'-\s*(\d{1,3})\s*%', title)
                if m: discount = int(m.group(1))
                
                # Отмечаем Game Pass особо
                prefix = f"{emoji}"
                if "game pass" in low or "gamepass" in low:
                    prefix = "🟢🟩 [GAME PASS]"
                
                if discount >= 40:
                    clean_title = re.sub(r'^\[[^\]]*\]\s*', '', title).strip()
                    deals.append({
                        "title": f"{prefix} −{discount}% | {clean_title}",
                        "link": "https://reddit.com" + p["permalink"],
                        "discount": discount
                    })
        except Exception as e:
            print(f"Reddit {query} сбой: {e}")

    deals.sort(key=lambda x: x["discount"], reverse=True)
    seen, unique = set(), []
    for d in deals:
        if d["link"] not in seen:
            seen.add(d["link"])
            unique.append(d)
    
    SOURCE_STATUS["deals"] = "✅" if unique else "⚠️"
    return unique[:10]

def get_rss_news():
    news, now = [], datetime.now(timezone.utc)
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:5]:
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if (now - pub) < timedelta(hours=24):
                        news.append({"title": entry.get("title", ""), "link": entry.get("link", ""), "source": src["name"]})
        except: pass
    SOURCE_STATUS["rss"] = "✅" if news else "⚠️"
    return news[:4]

def get_youtube_videos():
    videos = []
    for ch in YOUTUBE_CHANNELS:
        try:
            feed = feedparser.parse(ch["feed"])
            for entry in feed.entries[:1]:
                videos.append({"title": entry.get("title", ""), "link": entry.get("link", ""), "source": ch["name"]})
        except: pass
    SOURCE_STATUS["youtube"] = "✅" if videos else "⚠️"
    return videos[:3]

def publish_drops():
    freebies = get_freebies()
    deals = get_deals()

    if freebies:
        msg = "🔥 <b>БЕСПЛАТНЫЕ ИГРЫ ПРЯМО СЕЙЧАС!</b>\n\n"
        for i, f in enumerate(freebies, 1):
            msg += f"{i}. <b>{f['title']}</b>\n   🔗 <a href='{f['link']}'>Забрать</a>\n\n"
        msg += "⏰ <i>Успей, пока не закончилась раздача!</i>\n"
        msg += "🌟 <i>Обзоры игр — в @AlexPlayHub</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)

    if deals:
        msg = "💸 <b>ГОРЯЧИЕ СКИДКИ (от 40%)</b>\n\n"
        for i, d in enumerate(deals, 1):
            msg += f"{i}. <b>{d['title']}</b>\n   🔗 <a href='{d['link']}'>К магазину</a>\n\n"
        msg += "⏰ <i>Цены могут измениться в любой момент!</i>"
        send_to_telegram(DROPS_CHANNEL_ID, msg)

    if not freebies and not deals:
        send_to_telegram(DROPS_CHANNEL_ID, "🤖 <b>Пока тихо.</b>\nКрупных раздач и скидок не найдено. Мониторим 24/7! 🔔")
    print("Drops опубликован.")

def publish_hub_game():
    d = get_game_of_day()
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
    send_to_telegram(CHAT_ID, "🚨 <b>Сбои:</b>\n" + "\n".join(f"⚠️ {w}" for w in WARNINGS)[:4000])

def run_safe(name, func):
    try:
        func()
    except Exception as e:
        WARNINGS.append(f"{name}: {e}")
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
