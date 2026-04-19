import telebot
import requests
import re
import json
import os
import io
from datetime import datetime, timedelta
from telebot import types

# ==================== الإعدادات الرئيسية ====================
BOT_TOKEN = "8691417895:AAGwvcJP4rkFq5gfvfycS1lnMm4Q3FbTrVw"
ADMIN_ID = 7916842400

# ==================== قنوات الأزرار الشفافين ====================
CHANNEL_SUPER_MARIO = "https://t.me/super_mairo"       # قناة سوبر ماريو
CHANNEL_SUPER_CHAT  = "https://t.me/l_z_b"             # شات سوبر
CHANNEL_TON_PRICE   = "https://t.me/Ton_Mario"        # قناة TON price

# ==================== قناة تتبع سعر TON ====================
TON_PRICE_CHANNEL   = -1003549979137                   # ID قناة Egyptdraws

# ==================== الاشتراك الإجباري في الجروب ====================
GROUP_FORCE_CHANNELS = [
    {"id": "@super_mairo", "title": "قناة السوبر"},
    {"id": "@l_z_b",       "title": "جروب السوبر"},
]

# توقيت مصر UTC+3
EGY_OFFSET = 3

# معلومات المطور — بتتجلب تلقائياً من تيليجرام
_DEV_CACHE = {}

def get_developer_info():
    global _DEV_CACHE
    if _DEV_CACHE:
        return _DEV_CACHE
    try:
        chat = bot.get_chat(ADMIN_ID)
        name = chat.first_name or ""
        if chat.last_name:
            name += f" {chat.last_name}"
        username = f"@{chat.username}" if chat.username else f"tg://user?id={ADMIN_ID}"
        bio = chat.bio or "مطور البوت 🤖"
        _DEV_CACHE = {
            "name":     name,
            "username": username,
            "user_id":  ADMIN_ID,
            "bio":      bio,
        }
    except:
        _DEV_CACHE = {
            "name":     "المطور",
            "username": f"tg://user?id={ADMIN_ID}",
            "user_id":  ADMIN_ID,
            "bio":      "مطور البوت 🤖",
        }
    return _DEV_CACHE

bot = telebot.TeleBot(BOT_TOKEN)

# ==================== نظام الميم (مسح الرغي) ====================
import threading
import time

meme_mode_chats = set()
pending_deletes = {}
banned_members = {}       # {chat_id: set(user_ids)}
group_lock_links = set()  # جروبات مقفول فيها الروابط
group_lock_forward = set()# جروبات مقفول فيها التوجيه

# حماية السبام: {chat_id: {user_id: [timestamps]}}
spam_tracker = {}

def check_spam(chat_id, user_id):
    now = time.time()
    if chat_id not in spam_tracker:
        spam_tracker[chat_id] = {}
    if user_id not in spam_tracker[chat_id]:
        spam_tracker[chat_id][user_id] = []
    # شيل الرسايل الأقدم من دقيقة
    spam_tracker[chat_id][user_id] = [t for t in spam_tracker[chat_id][user_id] if now - t < 60]
    spam_tracker[chat_id][user_id].append(now)
    return len(spam_tracker[chat_id][user_id]) > 5

def schedule_delete(chat_id, msg_id, delay=90):
    key = (chat_id, msg_id)
    def do_delete():
        try:
            bot.delete_message(chat_id, msg_id)
        except:
            pass
        pending_deletes.pop(key, None)
    t = threading.Timer(delay, do_delete)
    t.daemon = True
    pending_deletes[key] = t
    t.start()

USERS_FILE = "users.json"
GROUPS_FILE = "groups.json"
FORCE_SUB_FILE = "force_sub.json"
CHANNELS_FILE = "channels.txt"

# ==================== تحميل البيانات ====================
def load_json(file):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, "r") as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    return []

def save_channels(channels):
    with open(CHANNELS_FILE, "w") as f:
        for ch in channels:
            f.write(f"{ch}\n")

# ==================== اشتراك إجباري للجروب ====================
def check_group_force_sub(user_id):
    """بيرجع قائمة القنوات اللي المستخدم مش مشترك فيها"""
    not_subbed = []
    for ch in GROUP_FORCE_CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ["left", "kicked"]:
                not_subbed.append(ch)
        except:
            not_subbed.append(ch)
    return not_subbed

def group_force_sub_keyboard(not_subbed, user_id=None):
    markup = types.InlineKeyboardMarkup()
    for ch in not_subbed:
        try:
            invite = bot.export_chat_invite_link(ch["id"])
        except:
            invite = f"https://t.me/{ch['id'].replace('@', '')}"
        markup.add(types.InlineKeyboardButton(f"📢 {ch['title']}", url=invite))
    cb = f"check_group_sub_{user_id}" if user_id else "check_group_sub_0"
    markup.add(types.InlineKeyboardButton("✅ اشتركت، تحقق", callback_data=cb))
    return markup

users = load_json(USERS_FILE)
groups = load_json(GROUPS_FILE)
force_channels = load_json(FORCE_SUB_FILE)
forced_channels = load_channels()

# ==================== إعدادات العملات ====================
EGP_PER_USD = 50.0

CRYPTO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether",
    "BNB": "binancecoin", "TON": "the-open-network", "TRX": "tron",
}
CRYPTO_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "USDT": "USDT",
    "BNB": "BNB", "TON": "Toncoin", "TRX": "TRON",
}

def ce(emoji_id, fallback="⭐"):
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

import random

# قايمة كل الأيموجيهات المميزة
ALL_EMOJIS = [
    "5355180574313060180", "5357272206206342962", "5354797987216265138",
    "5357581641420143839", "5357169569372866445", "5355057446190613905",
    "5355023563193619708", "5355332431471748210", "5355200176543799124",
    "5354973921961611463", "5215420556089776398", "5204242830687494041",
    "5381975814415866082", "5461128651477111908", "5472250091332993630",
    "5235794253149394263", "5462902520215002477", "5472239203590888751",
    "5400090058030075645", "5377336227533969892", "5417924076503062111",
    "5472279086657199080", "5992577678367005564", "5352550929046461287",
    "5433836586737357805", "5253475714384024341", "5404531586790086938",
    "5402376153157622159", "5404425513982774265", "5402456731039064202",
    "5927241068197187139", "5931718859366075705", "5929172914422156484",
    "5929158569231388216", "5933599273357675660", "5929545717583449337",
    "5929436084248251508", "5933948939530145209", "5472055112702629499",
    "5809952748363324368", "5355052884935345861", "5456543391636534278",
    "5251595639694848975", "5253495814830974755", "5379754740798217017",
    "5197269100878907942", "5253510310345600737", "5936147649253086101",
    "5251562950698759162", "5395587502079753683",
]

def rce():
    """أيموجي عشوائي مميز"""
    return ce(random.choice(ALL_EMOJIS), "✨")

def rce_list(n):
    """قايمة من n أيموجيهات مختلفة عشوائية"""
    pool = ALL_EMOJIS.copy()
    random.shuffle(pool)
    return [ce(pool[i % len(pool)], "✨") for i in range(n)]

CRYPTO_EMOJI = {
    "BTC": "₿",
    "ETH": "⟠",
    "USDT": ce("5472387796574418157", "💲"),
    "BNB": ce("5399926694653999517", "🟡"),
    "TON": ce("5251562950698759162", "💎"),
    "TRX": ce("5253495814830974755", "⚡"),
}
FIAT_SYMBOLS = {
    "usd": f'{ce("5251635900718282453", "💵")} دولار',
    "egp": f'{ce("5222161185138292290", "🇪🇬")} جنيه مصري',
    "eur": "💶 يورو",
    "sar": f'{ce("5224698145010624573", "🇸🇦")} ريال سعودي',
    "try": f'{ce("5228925659845242197", "🇹🇷")} ليرة تركية',
    "rub": f'{ce("5228853994020941586", "🇷🇺")} روبل روسي',
}
CRYPTO_ALIAS = {
    "btc": "BTC", "bitcoin": "BTC",
    "eth": "ETH", "ethereum": "ETH", "ether": "ETH",
    "usdt": "USDT", "tether": "USDT",
    "bnb": "BNB", "binance": "BNB",
    "ton": "TON", "toncoin": "TON",
    "trx": "TRX", "tron": "TRX",
    "بيتكوين": "BTC", "بتكوين": "BTC",
    "ايثريوم": "ETH", "اثيريوم": "ETH", "إيثريوم": "ETH",
    "تيثر": "USDT", "بينانس": "BNB",
    "تون": "TON", "التون": "TON",
    "ترون": "TRX", "تريكس": "TRX",
}
FIAT_ALIAS = {
    "usd": "usd", "dollar": "usd", "dollars": "usd",
    "eur": "eur", "euro": "eur", "euros": "eur",
    "sar": "sar", "riyal": "sar", "riyals": "sar",
    "try": "try", "lira": "try", "liras": "try",
    "rub": "rub", "ruble": "rub", "rubles": "rub",
    "ريال سعودي": "sar", "ليرة تركية": "try",
    "ليره تركيه": "try", "روبل روسي": "rub",
    "دولار": "usd", "دولارات": "usd",
    "يورو": "eur",
    "ريال": "sar", "ريالات": "sar",
    "ليره": "try", "ليرة": "try",
    "روبل": "rub",
    "جنيه": "egp", "جنيها": "egp", "جنيهات": "egp",
    "جنيه مصري": "egp", "egp": "egp", "pound": "egp", "pounds": "egp",
}

# ==================== تسجيل المستخدمين ====================
def register_user(message, notify=False):
    uid = str(message.from_user.id)
    is_new = uid not in users
    if is_new:
        users[uid] = {
            "name": message.from_user.full_name,
            "username": message.from_user.username or "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_json(USERS_FILE, users)
    if notify and is_new:
        username = message.from_user.username
        uname_display = f"@{username}" if username else "بدون يوزر"
        try:
            bot.send_message(
                ADMIN_ID,
                f'{ce("5253495814830974755","⚡")} <b>مستخدم جديد!</b>\n\n'
                f'{ce("5253510310345600737","🔗")} الاسم: {message.from_user.full_name}\n'
                f'{ce("5253510310345600737","🔗")} يوزر: {uname_display}\n'
                f'{ce("5873044297523140571","🆔")} ID: <code>{message.from_user.id}</code>\n'
                f'🕐 الوقت: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                parse_mode="HTML"
            )
        except: pass

def register_group(message):
    gid = str(message.chat.id)
    if gid not in groups:
        groups[gid] = {
            "title": message.chat.title or "جروب",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_json(GROUPS_FILE, groups)

# ==================== الاشتراك الإجباري ====================
def check_force_sub(user_id):
    not_subbed = []
    for ch_id, ch_title in force_channels.items():
        try:
            member = bot.get_chat_member(ch_id, user_id)
            if member.status in ["left", "kicked"]:
                not_subbed.append((ch_id, ch_title))
        except:
            not_subbed.append((ch_id, ch_title))
    return not_subbed

def force_sub_keyboard(not_subbed):
    markup = types.InlineKeyboardMarkup()
    for ch_id, ch_title in not_subbed:
        try:
            invite = bot.export_chat_invite_link(ch_id)
        except:
            invite = f"https://t.me/{ch_id.replace('@', '')}"
        markup.add(types.InlineKeyboardButton(f'📢 {ch_title}', url=invite))
    markup.add(types.InlineKeyboardButton(f'✅ تحققت من الاشتراك', callback_data="check_sub"))
    return markup

# ==================== لوحة الأدمن ====================
def admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ إضافة قناة إجبارية", callback_data="admin_add_force"),
        types.InlineKeyboardButton("🗑 حذف قناة إجبارية", callback_data="admin_del_force"),
        types.InlineKeyboardButton("📋 قنوات الاشتراك الإجباري", callback_data="admin_list_force"),
        types.InlineKeyboardButton("📢 إذاعة للمستخدمين", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
        types.InlineKeyboardButton("👥 عرض الأعضاء", callback_data="admin_users"),
    )
    return markup

def crypto_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("₿ BTC", callback_data="coin_BTC"),
        types.InlineKeyboardButton("⟠ ETH", callback_data="coin_ETH"),
        types.InlineKeyboardButton("💲 USDT", callback_data="coin_USDT"),
        types.InlineKeyboardButton("🟡 BNB", callback_data="coin_BNB"),
        types.InlineKeyboardButton("💎 TON", callback_data="coin_TON"),
        types.InlineKeyboardButton("⚡ TRX", callback_data="coin_TRX"),
    )
    return markup

# ==================== جلب أسعار الصرف ====================
def get_fx_rates():
    global EGP_PER_USD
    try:
        resp = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        rates = resp.json().get("rates", {})
        if rates.get("EGP"):
            fx = {
                "egp": rates["EGP"],
                "eur": rates.get("EUR", 0.92),
                "sar": rates.get("SAR", 3.75),
                "try": rates.get("TRY", 34.0),
                "rub": rates.get("RUB", 92.0),
                "iqd": rates.get("IQD", 1310.0),
            }
            EGP_PER_USD = fx["egp"]
            return fx
    except: pass
    try:
        url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
        resp = requests.get(url, timeout=10)
        rates = resp.json().get("usd", {})
        if rates.get("egp"):
            fx = {
                "egp": rates["egp"],
                "eur": rates.get("eur", 0.92),
                "sar": rates.get("sar", 3.75),
                "try": rates.get("try", 34.0),
                "rub": rates.get("rub", 92.0),
                "iqd": rates.get("iqd", 1310.0),
            }
            EGP_PER_USD = fx["egp"]
            return fx
    except: pass
    return {"egp": EGP_PER_USD, "eur": 0.92, "sar": 3.75, "try": 34.0, "rub": 92.0, "iqd": 1310.0}

# ==================== جلب أسعار العملات الرقمية ====================
_HEADERS = {
    "accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; CryptoBot/1.0)"
}

def _build_data_from_usd(usd_map, fx):
    """usd_map = {coin_id: usd_price} → data dict كامل"""
    data = {}
    for coin_id, usd_p in usd_map.items():
        if usd_p > 0:
            row = {"usd": usd_p}
            for fc, rate in fx.items():
                row[fc] = usd_p * rate
            data[coin_id] = row
    return data

def _fetch_ton_usd():
    """جلب سعر TON من مصادر متعددة"""
    # OKX
    try:
        r = requests.get("https://www.okx.com/api/v5/market/ticker?instId=TON-USDT", timeout=8, headers=_HEADERS)
        p = float(r.json()["data"][0]["last"])
        if p > 0: return p
    except: pass
    # Gate.io
    try:
        r = requests.get("https://api.gateio.ws/api/v4/spot/tickers?currency_pair=TON_USDT", timeout=8, headers=_HEADERS)
        p = float(r.json()[0]["last"])
        if p > 0: return p
    except: pass
    # Bybit
    try:
        r = requests.get("https://api.bybit.com/v5/market/tickers?category=spot&symbol=TONUSDT", timeout=8, headers=_HEADERS)
        p = float(r.json()["result"]["list"][0]["lastPrice"])
        if p > 0: return p
    except: pass
    return 0

# ==================== شارت سعر العملة ====================
CHART_ALIASES = {
    "شارت": True, "شارتات": True, "chart": True, "charts": True,
    "رسم": True, "بياني": True, "رسم بياني": True, "جراف": True, "graph": True,
}

CHART_PERIODS = {
    # ساعات محددة — بيرجع (hours, label)
    "ساعه": (1, "ساعة"), "ساعة": (1, "ساعة"), "1h": (1, "ساعة"),
    "ساعتين": (2, "ساعتين"), "2h": (2, "ساعتين"),
    "3ساعات": (3, "3 ساعات"), "3 ساعات": (3, "3 ساعات"), "3h": (3, "3 ساعات"),
    "4ساعات": (4, "4 ساعات"), "4 ساعات": (4, "4 ساعات"), "4h": (4, "4 ساعات"),
    "5ساعات": (5, "5 ساعات"), "5 ساعات": (5, "5 ساعات"), "5h": (5, "5 ساعات"),
    "6ساعات": (6, "6 ساعات"), "6 ساعات": (6, "6 ساعات"), "6h": (6, "6 ساعات"),
    "8ساعات": (8, "8 ساعات"), "8 ساعات": (8, "8 ساعات"), "8h": (8, "8 ساعات"),
    "12ساعه": (12, "12 ساعة"), "12ساعة": (12, "12 ساعة"), "12 ساعه": (12, "12 ساعة"), "12h": (12, "12 ساعة"),
    "24ساعه": (24, "24 ساعة"), "24ساعة": (24, "24 ساعة"), "24 ساعه": (24, "24 ساعة"), "24 ساعة": (24, "24 ساعة"), "24h": (24, "24 ساعة"),
    "يوم": (24, "24 ساعة"), "يومي": (24, "24 ساعة"), "1d": (24, "24 ساعة"),
    "اسبوع": (168, "7 أيام"), "أسبوع": (168, "7 أيام"), "اسبوعي": (168, "7 أيام"), "1w": (168, "7 أيام"),
    "شهر": (720, "30 يوم"), "شهري": (720, "30 يوم"), "1m": (720, "30 يوم"),
}

def parse_chart_request(text):
    """بيرجع (crypto_code, hours) أو None"""
    t = text.strip().lower()
    found_chart = False
    for kw in sorted(CHART_ALIASES.keys(), key=len, reverse=True):
        if kw in t:
            found_chart = True
            t = t.replace(kw, "").strip()
            break
    if not found_chart:
        return None

    # ابحث عن رقم + كلمة ساعات ديناميكي (مثلاً "3 ساعات", "5ساعات")
    hours = 24  # default
    label = "24 ساعة"
    num_hour_match = re.search(r'(\d+)\s*ساع[هة]?', t)
    if num_hour_match:
        h = int(num_hour_match.group(1))
        hours = h
        label = f"{h} ساعة" if h > 2 else ("ساعة" if h == 1 else "ساعتين")
    else:
        for kw, (h, lbl) in sorted(CHART_PERIODS.items(), key=lambda x: len(x[0]), reverse=True):
            if kw in t:
                hours = h
                label = lbl
                t = t.replace(kw, "").strip()
                break

    # ابحث عن العملة
    for alias in sorted(CRYPTO_ALIAS.keys(), key=len, reverse=True):
        if alias in t:
            return (CRYPTO_ALIAS[alias], hours, label)
    return None

def _fetch_klines(crypto_code, hours):
    """بيجيب بيانات الأسعار — hours = عدد الساعات"""
    coin_id = CRYPTO_IDS.get(crypto_code)
    days = max(1, hours / 24)  # للـ APIs اللي بتاخد days

    # 1) CoinGecko
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}"
        r = requests.get(url, timeout=15, headers=_HEADERS)
        r.raise_for_status()
        data = r.json().get("prices", [])
        if len(data) >= 2:
            return data
    except: pass

    # 2) Binance — interval ساعة دايماً
    try:
        sym_map = {"BTC":"BTCUSDT","ETH":"ETHUSDT","BNB":"BNBUSDT","TRX":"TRXUSDT","TON":"TONUSDT"}
        sym = sym_map.get(crypto_code)
        if sym:
            limit = min(hours, 500)
            r = requests.get(
                f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&limit={limit}",
                timeout=10, headers=_HEADERS
            )
            r.raise_for_status()
            klines = r.json()
            if isinstance(klines, list) and len(klines) >= 2:
                return [[k[0], float(k[4])] for k in klines]
    except: pass

    # 3) OKX
    try:
        okx_map = {"BTC":"BTC-USDT","ETH":"ETH-USDT","BNB":"BNB-USDT","TRX":"TRX-USDT","TON":"TON-USDT"}
        sym = okx_map.get(crypto_code)
        if sym:
            limit = min(hours, 300)
            r = requests.get(
                f"https://www.okx.com/api/v5/market/candles?instId={sym}&bar=1H&limit={limit}",
                timeout=10, headers=_HEADERS
            )
            r.raise_for_status()
            candles = list(reversed(r.json().get("data", [])))
            if len(candles) >= 2:
                return [[int(c[0]), float(c[4])] for c in candles]
    except: pass

    # 4) Gate.io
    try:
        gate_map = {"BTC":"BTC_USDT","ETH":"ETH_USDT","BNB":"BNB_USDT","TRX":"TRX_USDT","TON":"TON_USDT"}
        sym = gate_map.get(crypto_code)
        if sym:
            limit = min(hours, 500)
            r = requests.get(
                f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}&interval=1h&limit={limit}",
                timeout=10, headers=_HEADERS
            )
            r.raise_for_status()
            candles = r.json()
            if isinstance(candles, list) and len(candles) >= 2:
                return [[int(c[0]) * 1000, float(c[2])] for c in candles]
    except: pass

    return None

def build_price_history(crypto_code, hours=24, label="24 ساعة"):
    """بيرجع رسالة نصية فيها سعر كل ساعة بالدولار والجنيه"""
    prices_data = _fetch_klines(crypto_code, hours)
    if not prices_data or len(prices_data) < 2:
        return None

    fx = get_fx_rates()
    egp_rate = fx.get("egp", 50.0)

    # خد آخر (hours) نقطة بالظبط — كل نقطة = ساعة
    points = [(p[0], p[1]) for p in prices_data]
    points = points[-hours:]  # آخر X ساعة بالظبط

    coin_name = CRYPTO_NAMES[crypto_code]
    first_price = points[0][1]
    last_price  = points[-1][1]
    total_change = ((last_price - first_price) / first_price) * 100
    total_arrow = "📈" if last_price >= first_price else "📉"

    lines = [f"{total_arrow} <b>تغيرات {coin_name} ({crypto_code})</b> — آخر {label}\n"]

    prev_price = None
    for ts, price in points:
        dt = datetime.utcfromtimestamp(ts / 1000 + EGY_OFFSET * 3600)
        time_str = dt.strftime("%H:%M") if hours <= 48 else dt.strftime("%d/%m %H:%M")

        if prev_price is None:
            arrow = "🔸"
        elif price > prev_price:
            arrow = "▲"
        elif price < prev_price:
            arrow = "▼"
        else:
            prev_price = price
            continue

        egp_price = price * egp_rate
        lines.append(
            f"<blockquote>{arrow} {time_str}  —  "
            f"<code>${fmt(price)}</code>  |  "
            f"<code>{fmt(egp_price)} ج</code></blockquote>"
        )
        prev_price = price

    change_arrow = "▲" if total_change >= 0 else "▼"
    lines.append(
        f"<blockquote>{change_arrow} <b>إجمالي التغيير: {abs(total_change):.2f}%</b></blockquote>"
    )
    lines.append(
        f"<blockquote>💰 السعر الحالي: <code>${fmt(last_price)}</code>  |  "
        f"<code>{fmt(last_price * egp_rate)} ج</code></blockquote>"
    )

    return "\n".join(lines)

# ==================== سعر الدولار في السوق السوداء ====================
BLACK_DOLLAR_ALIASES = [
    "دولار سوداء", "الدولار السوداء", "دولار السوداء",
    "دولار سودا", "الدولار السودا",
    "سوق سوداء", "السوق السوداء",
    "black dollar", "black market", "black market dollar",
    "دولار موازي", "الدولار الموازي", "سعر موازي",
]

def get_black_market_dollar():
    """بيرجع dict فيه buy/sell/official أو None"""
    # مصدر 1: egcurrency.com (موقع مصري متخصص)
    try:
        r = requests.get("https://egcurrency.com/ar/currency/usd-egp-black-market", timeout=10,
                         headers={**_HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        html = r.text
        # استخراج الأرقام
        buy_m  = re.search(r'شراء[^<]*<[^>]+>([0-9.]+)', html)
        sell_m = re.search(r'بيع[^<]*<[^>]+>([0-9.]+)', html)
        if buy_m and sell_m:
            return {"buy": float(buy_m.group(1)), "sell": float(sell_m.group(1))}
    except: pass

    # مصدر 2: API مباشر من egcurrency
    try:
        r = requests.get("https://egcurrency.com/api/black-market/usd", timeout=10, headers=_HEADERS)
        d = r.json()
        if d.get("buy"):
            return {"buy": float(d["buy"]), "sell": float(d.get("sell", d["buy"]))}
    except: pass

    # مصدر 3: صفحة exchange rate
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=8, headers=_HEADERS)
        official = r.json().get("rates", {}).get("EGP", 0)
        if official > 0:
            # السوق السوداء تقريباً 3-5% أعلى من الرسمي (fallback تقريبي)
            return {"buy": round(official * 1.03, 2), "sell": round(official * 1.05, 2), "approx": True}
    except: pass

    return None

def build_black_dollar_result():
    data = get_black_market_dollar()
    if not data:
        return "❌ مش قادر أجيب سعر السوق السوداء دلوقتي، جرب تاني!"

    buy  = data.get("buy", 0)
    sell = data.get("sell", 0)
    approx = data.get("approx", False)

    note = "\n<i>⚠️ سعر تقريبي</i>" if approx else ""
    now  = datetime.now().strftime("%H:%M")

    return (
        f'{ce("5222161185138292290","🇪🇬")} <b>الدولار في السوق السوداء المصرية</b>\n\n'
        f'<blockquote>'
        f'{ce("5251635900718282453","💵")} شراء: <b><code>{fmt(buy)}</code></b> جنيه\n'
        f'{ce("5251635900718282453","💵")} بيع:  <b><code>{fmt(sell)}</code></b> جنيه'
        f'</blockquote>'
        f'{note}\n'
        f'<i>🕐 {now}</i>'
    )

def get_prices():
    fx = get_fx_rates()

    # --- 1) CoinGecko ---
    try:
        ids = ",".join(CRYPTO_IDS.values())
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        resp = requests.get(url, timeout=12, headers=_HEADERS)
        resp.raise_for_status()
        raw = resp.json()
        if raw and "bitcoin" in raw and raw["bitcoin"].get("usd", 0) > 0:
            usd_map = {cid: raw[cid].get("usd", 0) for cid in raw}
            if not usd_map.get("the-open-network"):
                ton_p = _fetch_ton_usd()
                if ton_p > 0:
                    usd_map["the-open-network"] = ton_p
            data = _build_data_from_usd(usd_map, fx)
            if data:
                return data
    except: pass

    # --- 2) Binance ---
    try:
        pairs = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT", "TRX": "TRXUSDT"}
        r = requests.get("https://api.binance.com/api/v3/ticker/price", timeout=10, headers=_HEADERS)
        r.raise_for_status()
        tickers = {t["symbol"]: float(t["price"]) for t in r.json()}
        usd_map = {}
        for code, sym in pairs.items():
            p = tickers.get(sym, 0)
            if p > 0:
                usd_map[CRYPTO_IDS[code]] = p
        usd_map["tether"] = 1.0
        ton_p = _fetch_ton_usd()
        if ton_p > 0:
            usd_map["the-open-network"] = ton_p
        if "bitcoin" in usd_map:
            return _build_data_from_usd(usd_map, fx)
    except: pass

    # --- 3) Kraken + TON fallback ---
    try:
        kraken_map = {"BTC": "XXBTZUSD", "ETH": "XETHZUSD", "TRX": "TRXUSD"}
        r = requests.get("https://api.kraken.com/0/public/Ticker?pair=XXBTZUSD,XETHZUSD,TRXUSD", timeout=10, headers=_HEADERS)
        r.raise_for_status()
        result = r.json().get("result", {})
        usd_map = {}
        for code, pair in kraken_map.items():
            c = result.get(pair, {})
            p = float(c.get("c", [0])[0]) if c.get("c") else 0
            if p > 0:
                usd_map[CRYPTO_IDS[code]] = p
        usd_map["tether"] = 1.0
        ton_p = _fetch_ton_usd()
        if ton_p > 0:
            usd_map["the-open-network"] = ton_p
        if "bitcoin" in usd_map:
            return _build_data_from_usd(usd_map, fx)
    except: pass

    # --- 4) CoinCap ---
    try:
        coincap_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "USDT": "tether",
            "BNB": "binance-coin", "TON": "toncoin", "TRX": "tron"
        }
        r = requests.get("https://api.coincap.io/v2/assets?limit=100", timeout=10, headers=_HEADERS)
        r.raise_for_status()
        assets = {a["id"]: float(a["priceUsd"] or 0) for a in r.json().get("data", [])}
        usd_map = {}
        for code, cid in coincap_map.items():
            p = assets.get(cid, 0)
            if p > 0:
                usd_map[CRYPTO_IDS[code]] = p
        if not usd_map.get("the-open-network"):
            ton_p = _fetch_ton_usd()
            if ton_p > 0:
                usd_map["the-open-network"] = ton_p
        if "bitcoin" in usd_map:
            return _build_data_from_usd(usd_map, fx)
    except: pass

    return None

def get_usd_rates(prices):
    fx = get_fx_rates()
    rates = {"usd": 1.0}
    rates.update(fx)
    return rates

# ==================== تنسيق الأرقام ====================
def fmt(n):
    if n == 0: return "0"
    if n >= 1_000_000: return f"{n:,.0f}"
    elif n >= 1000: return f"{n:,.2f}".rstrip("0").rstrip(".")
    elif n >= 1: return f"{n:.4f}".rstrip("0").rstrip(".")
    elif n >= 0.0001: return f"{n:.6f}".rstrip("0").rstrip(".")
    else: return f"{n:.8f}".rstrip("0").rstrip(".")

# ==================== نجوم تيليجرام ====================
STARS_PER_USD = 1000 / 13.0  # السعر الرسمي من Fragment: 1000 نجمة = $13

STARS_ALIAS = [
    "نجمه", "نجمة", "نجوم", "النجوم", "النجمه", "النجمة",
    "ستار", "ستارز", "stars", "star", "⭐"
]

def build_stars_result(amount):
    fx = get_fx_rates()
    usd = amount / STARS_PER_USD
    egp = usd * fx.get("egp", EGP_PER_USD)
    eur = usd * fx.get("eur", 0.92)
    sar = usd * fx.get("sar", 3.75)

    # سعر TON
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd",
            timeout=10
        )
        ton_usd = resp.json().get("the-open-network", {}).get("usd", 0)
    except:
        ton_usd = 0

    def bq(line):
        return f"<blockquote>{line}</blockquote>"

    lines = [
        bq(f'{ce("5355052884935345861", "⭐")} <b>{fmt(amount)} نجمة Telegram Stars</b>'),
        bq(f'{ce("5251635900718282453", "💵")} دولار: <code>{fmt(usd)}</code>'),
        bq(f'{ce("5222161185138292290", "🇪🇬")} جنيه مصري: <code>{fmt(egp)}</code>'),
        bq(f'💶 يورو: <code>{fmt(eur)}</code>'),
        bq(f'{ce("5224698145010624573", "🇸🇦")} ريال سعودي: <code>{fmt(sar)}</code>'),
    ]
    if ton_usd > 0:
        ton = usd / ton_usd
        lines.append(bq(f'{ce("5251562950698759162", "💎")} Toncoin: <code>{fmt(ton)} TON</code>'))

    lines.append(bq(f'<i>{ce("5355052884935345861", "⭐")} السعر على Fragment: 1000 نجمة = $13.00</i>'))
    return "\n".join(lines)

def parse_stars(text):
    text_lower = text.strip().lower()
    # لازم الرسالة تكون رقم + كلمة النجمة بس ومفيش أي كلام تاني
    found_alias = None
    for alias in sorted(STARS_ALIAS, key=len, reverse=True):
        if alias in text_lower:
            found_alias = alias
            break
    if not found_alias:
        return None
    # شيل الرقم والـ alias وشوف لو فضل حاجه
    temp = text_lower.replace(found_alias, "").strip()
    temp = re.sub(r"[\d,\.]+", "", temp).strip()
    if temp:
        return None
    num = re.search(r"[\d,\.]+", text_lower)
    amount = float(num.group().replace(",", "")) if num else 1.0
    return amount

def parse_message(text):
    text_lower = text.strip().lower()
    for alias in sorted(FIAT_ALIAS.keys(), key=len, reverse=True):
        if alias in text_lower:
            num = re.search(r"[\d,\.]+", text_lower)
            amount = float(num.group().replace(",", "")) if num else 1.0
            return ("fiat", amount, FIAT_ALIAS[alias])
    for alias in sorted(CRYPTO_ALIAS.keys(), key=len, reverse=True):
        if alias in text_lower:
            num = re.search(r"[\d,\.]+", text_lower)
            amount = float(num.group().replace(",", "")) if num else 1.0
            return ("crypto", amount, CRYPTO_ALIAS[alias])
    return None

def build_crypto_result(amount, crypto_code, prices):
    coin_id = CRYPTO_IDS[crypto_code]
    coin_data = prices.get(coin_id, {})
    if not coin_data:
        return f"❌ مش قادر أجيب سعر {CRYPTO_NAMES[crypto_code]} دلوقتي!"
    lines = [f'{ce("5276081871019591962", "🪙")} <b>{fmt(amount)} {CRYPTO_NAMES[crypto_code]} ({crypto_code})</b>\n']
    lines.append(f'{ce("5310170944843579391", "💱")} <b>بالعملات العادية:</b>')
    for fiat, symbol in FIAT_SYMBOLS.items():
        price = coin_data.get(fiat, 0)
        if price > 0:
            lines.append(f"{symbol}: <code>{fmt(price * amount)}</code>")
    lines.append(f'\n{ce("5253510310345600737", "🔗")} <b>بالعملات الرقمية:</b>')
    usd_val = coin_data.get("usd", 0) * amount
    for code, cid in CRYPTO_IDS.items():
        if code == crypto_code: continue
        other_usd = prices.get(cid, {}).get("usd", 0)
        if other_usd > 0:
            lines.append(f"{CRYPTO_EMOJI[code]} {CRYPTO_NAMES[code]}: <code>{fmt(usd_val / other_usd)} {code}</code>")
    lines.append(f'\n<i>{ce("5395587502079753683", "📊")} Real-time prices</i>')
    return "\n".join(lines)

def build_fiat_result(amount, fiat_code, prices):
    fiat_name = FIAT_SYMBOLS.get(fiat_code, fiat_code.upper())
    lines = [f'{ce("5310170944843579391", "💱")} <b>{fmt(amount)} {fiat_name}</b>\n']
    usd_rates = get_usd_rates(prices)
    rate = usd_rates.get(fiat_code, 0)
    if rate <= 0: return "❌ مش قادر أحسب السعر دلوقتي!"
    amount_usd = amount / rate
    lines.append(f'{ce("5310170944843579391", "💱")} <b>بالعملات العادية:</b>')
    if fiat_code != "usd":
        lines.append(f'{ce("5251635900718282453", "💵")} دولار: <code>{fmt(amount_usd)}</code>')
    lines.append(f'{ce("5222161185138292290", "🇪🇬")} جنيه مصري: <code>{fmt(amount_usd * usd_rates.get("egp", EGP_PER_USD))}</code>')
    for fiat in ["eur", "sar", "try", "rub"]:
        if fiat == fiat_code: continue
        r = usd_rates.get(fiat, 0)
        if r > 0:
            lines.append(f"{FIAT_SYMBOLS[fiat]}: <code>{fmt(amount_usd * r)}</code>")
    lines.append(f'\n{ce("5253510310345600737", "🔗")} <b>بالعملات الرقمية:</b>')
    for code, cid in CRYPTO_IDS.items():
        usd_p = prices.get(cid, {}).get("usd", 0)
        if usd_p > 0:
            lines.append(f"{CRYPTO_EMOJI[code]} {CRYPTO_NAMES[code]}: <code>{fmt(amount_usd / usd_p)} {code}</code>")
    lines.append(f'\n<i>{ce("5395587502079753683", "📊")} Real-time prices</i>')
    return "\n".join(lines)

admin_state = {}
PROTECTED_WORDS_FILE = "protected_words.json"

# ==================== نظام اللغات ====================
LANG_TEXTS = {
    "ar": {
        "choose_lang": "👋 أهلاً! اختار لغتك:",
        "welcome": "أهلاً",
        "main_menu_text": "اختار من القائمة:",
        "btn_crypto":    "💰 العملات الرقمية",
        "btn_stars":     "⭐ نجوم تيليجرام",
        "btn_groups":    "👥 إضافة للمجموعات",
        "btn_cash":      "💸 تحويل كاش",
        "btn_calc":      "🧮 الآلة الحاسبة",
        "btn_translate": "🌐 ترجمة",
        "btn_group_tools": "🛡 أدوات الجروب",
        "btn_back":      "🔙 رجوع",
        "btn_add_group": "➕ أضفني لمجموعتك",
        "crypto_title":  "اختار العملة:",
        "stars_info": (
            f'{ce("5355052884935345861","⭐")} <b>نجوم تيليجرام</b>\n\n'
            f'{ce("5456543391636534278","🔸")} اكتب عدد النجوم اللي عايز تعرف سعرها\n\n'
            f'{ce("5253510310345600737","📝")} <b>مثال:</b>\n'
            f'<blockquote><code>100 نجمه</code>\n<code>500 نجمة</code>\n<code>1000 stars</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} هرد عليك بالسعر بالجنيه والدولار والتون فورًا'
        ),
        "groups_info": (
            f'{ce("6033125983572201397","👥")} <b>إضافة البوت للمجموعات</b>\n\n'
            f'{ce("5456543391636534278","🔸")} ضيف البوت في جروبك وهيشتغل معاك:\n\n'
            f'{ce("5251562950698759162","💎")} أسعار العملات الرقمية\n'
            f'{ce("5355052884935345861","⭐")} أسعار النجوم\n'
            f'{ce("5251595639694848975","✅")} فلتر الرسائل\n'
            f'{ce("5936147649253086101","🙋")} قبول طلبات الانضمام تلقائياً\n'
        ),
        "group_tools_info": (
            f'{ce("5253495814830974755","🛡")} <b>أدوات الجروب</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} ضيف البوت أدمن في جروبك وهيشتغل معاك</blockquote>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>كتم عضو</b>\n'
            f'رد على رسالته واكتب: <code>كتم</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>الغاء كتم</b>\n'
            f'اكتب: <code>الغاء كتم @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>طرد عضو</b>\n'
            f'رد على رسالته واكتب: <code>طرد</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>الغاء طرد</b>\n'
            f'اكتب: <code>الغاء طرد @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>قفل الروابط</b>\n'
            f'اكتب: <code>قفل روابط</code> — وأي رابط يتمسح تلقائي</blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>قفل التوجيه</b>\n'
            f'اكتب: <code>قفل تحويل</code> — وأي رسالة محولة تتمسح</blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","🎉")} <b>ترحيب تلقائي</b>\n'
            f'البوت بيرحب بكل عضو جديد يدخل الجروب باسمه</blockquote>'
        ),
        "btn_beautify": "✨ تزيين الرسائل",
        "btn_protection": "🛡 حماية الجروب",
        "protection_info": (
            f'{ce("5253495814830974755","🛡")} <b>حماية الجروب</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} ضيف البوت أدمن في جروبك وهيشتغل معاك</blockquote>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>كتم عضو</b>\n'
            f'اكتب: <code>كتم @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>الغاء كتم</b>\n'
            f'اكتب: <code>الغاء كتم @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>طرد عضو</b>\n'
            f'اكتب: <code>طرد @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>الغاء طرد</b>\n'
            f'اكتب: <code>الغاء طرد @يوزر</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>قفل الروابط</b>\n'
            f'اكتب: <code>قفل روابط</code> ← أي رابط يتمسح تلقائي</blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>قفل التوجيه</b>\n'
            f'اكتب: <code>قفل تحويل</code> ← أي توجيه يتمسح تلقائي</blockquote>\n\n'
            f'<blockquote>{ce("5395587502079753683","⚡")} <b>حماية سبام تلقائية</b>\n'
            f'أكتر من 5 رسايل في دقيقة = كتم تلقائي</blockquote>'
        ),
        "beautify_info": (
            f'{ce("5355052884935345861","✨")} <b>تزيين الرسائل</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} ابعتلي الرسالة اللي عايز تزينها</blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","📝")} البوت هيزين كل سطر بأيموجيهات مميزة\n'
            f'ويحط فواصل جميلة بين الأسطر</blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} ابعت رسالتك دلوقتي وهرد عليك بنسخة مزينة</blockquote>'
        ),
        "cash_info": (
            f'{ce("5253495814830974755","💸")} <b>تحويل كاش</b>\n\n'
            f'{ce("5456543391636534278","🔸")} اكتب المبلغ ورقم الهاتف جنب بعض\n\n'
            f'{ce("5253510310345600737","📝")} <b>مثال:</b>\n'
            f'<blockquote><code>100 01157110015</code>\n<code>01157110015 500</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} هرد عليك بكودات التحويل لفودافون وأورانج واتصالات جاهزة للنسخ'
        ),
        "calc_info": (
            f'{ce("5395587502079753683","🧮")} <b>الآلة الحاسبة</b>\n\n'
            f'{ce("5456543391636534278","🔸")} اكتب أي عملية حسابية وهرد عليك بالناتج\n\n'
            f'{ce("5253510310345600737","📝")} <b>أمثلة:</b>\n'
            f'<blockquote><code>100 * 5</code>\n<code>1500 / 3</code>\n<code>250 + 750</code>\n<code>1000 - 350</code>\n<code>2 ^ 10</code>\n<code>sqrt(144)</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} يدعم الجمع والطرح والضرب والقسمة والأس والجذر التربيعي'
        ),
        "translate_info": (
            f'{ce("5379754740798217017","🌐")} <b>ترجمة</b>\n\n'
            f'{ce("5456543391636534278","🔸")} اكتب "ترجمة" أو "translate" قبل النص\n\n'
            f'{ce("5253510310345600737","📝")} <b>أمثلة:</b>\n'
            f'<blockquote><code>ترجمة hello world</code>\n<code>translate مرحبا بالعالم</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} يترجم من وإلى أي لغة للعربي تلقائياً'
        ),
    },
    "en": {
        "choose_lang": "👋 Hello! Choose your language:",
        "welcome": "Hello",
        "main_menu_text": "Choose from the menu:",
        "btn_crypto":    "💰 Crypto Prices",
        "btn_stars":     "⭐ Telegram Stars",
        "btn_groups":    "👥 Add to Groups",
        "btn_cash":      "💸 Cash Transfer",
        "btn_calc":      "🧮 Calculator",
        "btn_translate": "🌐 Translate",
        "btn_group_tools": "🛡 Group Tools",
        "btn_back":      "🔙 Back",
        "btn_add_group": "➕ Add me to your group",
        "crypto_title":  "Choose a coin:",
        "stars_info": (
            f'{ce("5355052884935345861","⭐")} <b>Telegram Stars</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Type the number of stars to check the price\n\n'
            f'{ce("5253510310345600737","📝")} <b>Example:</b>\n'
            f'<blockquote><code>100 stars</code>\n<code>500 star</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} I\'ll reply instantly with USD, EGP & TON price'
        ),
        "groups_info": (
            f'{ce("6033125983572201397","👥")} <b>Add Bot to Groups</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Add the bot to your group:\n\n'
            f'{ce("5251562950698759162","💎")} Crypto prices\n'
            f'{ce("5355052884935345861","⭐")} Stars prices\n'
            f'{ce("5251595639694848975","✅")} Message filter\n'
            f'{ce("5936147649253086101","🙋")} Auto join request approval\n'
        ),
        "cash_info": (
            f'{ce("5253495814830974755","💸")} <b>Cash Transfer</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Type the amount and phone number together\n\n'
            f'{ce("5253510310345600737","📝")} <b>Example:</b>\n'
            f'<blockquote><code>100 01157110015</code>\n<code>01157110015 500</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} I\'ll reply with transfer codes for Vodafone, Orange & Etisalat'
        ),
        "calc_info": (
            f'{ce("5395587502079753683","🧮")} <b>Calculator</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Type any math expression\n\n'
            f'{ce("5253510310345600737","📝")} <b>Examples:</b>\n'
            f'<blockquote><code>100 * 5</code>\n<code>1500 / 3</code>\n<code>sqrt(144)</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Supports +, -, *, /, ^ and sqrt'
        ),
        "translate_info": (
            f'{ce("5379754740798217017","🌐")} <b>Translate</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Type "translate" before any text\n\n'
            f'{ce("5253510310345600737","📝")} <b>Example:</b>\n'
            f'<blockquote><code>translate مرحبا</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Translates anything to Arabic automatically'
        ),
        "group_tools_info": (
            f'{ce("5253495814830974755","🛡")} <b>Group Tools</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} Add the bot as admin in your group first</blockquote>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>Mute member</b>\n'
            f'Reply to their message and type: <code>كتم</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>Unmute member</b>\n'
            f'Type: <code>الغاء كتم @username</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>Ban member</b>\n'
            f'Reply to their message and type: <code>طرد</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>Unban member</b>\n'
            f'Type: <code>الغاء طرد @username</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>Lock links</b>\n'
            f'Type: <code>قفل روابط</code></blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>Lock forwards</b>\n'
            f'Type: <code>قفل تحويل</code></blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","🎉")} <b>Auto welcome</b>\n'
            f'Bot welcomes every new member by name</blockquote>'
        ),
        "btn_beautify": "✨ Beautify Messages",
        "btn_protection": "🛡 Group Protection",
        "protection_info": (
            f'{ce("5253495814830974755","🛡")} <b>Group Protection</b>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>Mute:</b> <code>كتم @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>Unmute:</b> <code>الغاء كتم @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>Ban:</b> <code>طرد @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>Unban:</b> <code>الغاء طرد @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>Lock links:</b> <code>قفل روابط</code></blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>Lock forwards:</b> <code>قفل تحويل</code></blockquote>\n\n'
            f'<blockquote>{ce("5395587502079753683","⚡")} <b>Auto spam protection</b>\n'
            f'5+ messages/min = auto mute</blockquote>'
        ),
        "beautify_info": (
            f'{ce("5355052884935345861","✨")} <b>Beautify Messages</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} Send me the message you want to beautify</blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","📝")} The bot will add fancy emojis to each line\n'
            f'and beautiful separators between lines</blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} Send your message now and I\'ll reply with a beautified version</blockquote>'
        ),
    },
    "ru": {
        "choose_lang": "👋 Привет! Выбери язык:",
        "welcome": "Привет",
        "main_menu_text": "Выбери из меню:",
        "btn_crypto":    "💰 Криптовалюты",
        "btn_stars":     "⭐ Звёзды Telegram",
        "btn_groups":    "👥 Добавить в группы",
        "btn_cash":      "💸 Перевод кэш",
        "btn_calc":      "🧮 Калькулятор",
        "btn_translate": "🌐 Перевод",
        "btn_group_tools": "🛡 Инструменты группы",
        "btn_back":      "🔙 Назад",
        "btn_add_group": "➕ Добавить меня в группу",
        "crypto_title":  "Выбери монету:",
        "stars_info": (
            f'{ce("5355052884935345861","⭐")} <b>Звёзды Telegram</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Напиши количество звёзд\n\n'
            f'{ce("5253510310345600737","📝")} <b>Пример:</b>\n'
            f'<blockquote><code>100 stars</code>\n<code>500 star</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Отвечу ценой в USD, EGP и TON сразу'
        ),
        "groups_info": (
            f'{ce("6033125983572201397","👥")} <b>Добавить бота в группы</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Добавь бота в свою группу:\n\n'
            f'{ce("5251562950698759162","💎")} Цены криптовалют\n'
            f'{ce("5355052884935345861","⭐")} Цены звёзд\n'
            f'{ce("5251595639694848975","✅")} Фильтр сообщений\n'
            f'{ce("5936147649253086101","🙋")} Авто-подтверждение заявок\n'
        ),
        "cash_info": (
            f'{ce("5253495814830974755","💸")} <b>Перевод кэш</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Напиши сумму и номер телефона рядом\n\n'
            f'{ce("5253510310345600737","📝")} <b>Пример:</b>\n'
            f'<blockquote><code>100 01157110015</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Отвечу кодами для Vodafone, Orange и Etisalat'
        ),
        "calc_info": (
            f'{ce("5395587502079753683","🧮")} <b>Калькулятор</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Напиши любое математическое выражение\n\n'
            f'{ce("5253510310345600737","📝")} <b>Примеры:</b>\n'
            f'<blockquote><code>100 * 5</code>\n<code>sqrt(144)</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Поддерживает +, -, *, /, ^ и sqrt'
        ),
        "translate_info": (
            f'{ce("5379754740798217017","🌐")} <b>Перевод</b>\n\n'
            f'{ce("5456543391636534278","🔸")} Напиши "translate" перед текстом\n\n'
            f'{ce("5253510310345600737","📝")} <b>Пример:</b>\n'
            f'<blockquote><code>translate مرحبا</code></blockquote>\n\n'
            f'{ce("5251595639694848975","✅")} Переводит всё на арабский автоматически'
        ),
        "group_tools_info": (
            f'{ce("5253495814830974755","🛡")} <b>Инструменты группы</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} Добавь бота как администратора</blockquote>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>Кик участника</b>\n'
            f'Ответь на сообщение и напиши: <code>كتم</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>Снять кик</b>\n'
            f'Напиши: <code>الغاء كتم @username</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>Бан участника</b>\n'
            f'Ответь на сообщение и напиши: <code>طرد</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>Снять бан</b>\n'
            f'Напиши: <code>الغاء طرد @username</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>Блокировка ссылок</b>\n'
            f'Напиши: <code>قفل روابط</code></blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>Блокировка пересылки</b>\n'
            f'Напиши: <code>قفل تحويل</code></blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","🎉")} <b>Авто-приветствие</b>\n'
            f'Бот приветствует каждого нового участника</blockquote>'
        ),
        "btn_beautify": "✨ Украсить сообщение",
        "btn_protection": "🛡 Защита группы",
        "protection_info": (
            f'{ce("5253495814830974755","🛡")} <b>Защита группы</b>\n\n'
            f'<blockquote>{ce("5253495814830974755","🔇")} <b>Кик:</b> <code>كتم @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","🔊")} <b>Снять кик:</b> <code>الغاء كتم @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5197269100878907942","🚫")} <b>Бан:</b> <code>طرد @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} <b>Снять бан:</b> <code>الغاء طرد @user</code></blockquote>\n\n'
            f'<blockquote>{ce("5379754740798217017","🔗")} <b>Блок ссылок:</b> <code>قفل روابط</code></blockquote>\n\n'
            f'<blockquote>{ce("5936147649253086101","↩️")} <b>Блок пересылки:</b> <code>قفل تحويل</code></blockquote>'
        ),
        "beautify_info": (
            f'{ce("5355052884935345861","✨")} <b>Украсить сообщение</b>\n\n'
            f'<blockquote>{ce("5456543391636534278","🔸")} Отправь мне сообщение для украшения</blockquote>\n\n'
            f'<blockquote>{ce("5253510310345600737","📝")} Бот добавит красивые эмодзи к каждой строке\n'
            f'и красивые разделители между строками</blockquote>\n\n'
            f'<blockquote>{ce("5251595639694848975","✅")} Отправь сообщение и я отвечу украшенной версией</blockquote>'
        ),
    },
}
def get_lang(uid):
    """بيرجع اللغه المؤقته للمستخدم لو موجوده، غير كده عربي"""
    return user_lang.get(uid, "ar")

# قاموس مؤقت للغه المستخدم (في الميموري بس - بيتمسح لما البوت يريستارت)
user_lang = {}

def lang_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("🇪🇬 العربية", callback_data="lang_ar"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
    )
    return markup

def main_menu_keyboard(lang):
    t = LANG_TEXTS[lang]
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t["btn_crypto"],    callback_data="menu_crypto"),
        types.InlineKeyboardButton(t["btn_stars"],     callback_data="menu_stars"),
        types.InlineKeyboardButton(t["btn_cash"],      callback_data="menu_cash"),
        types.InlineKeyboardButton(t["btn_beautify"],    callback_data="menu_beautify"),
        types.InlineKeyboardButton(t["btn_groups"],      callback_data="menu_groups"),
    )
    return markup

def groups_keyboard(lang):
    t = LANG_TEXTS[lang]
    bot_username = bot.get_me().username
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(t["btn_add_group"], url=f"https://t.me/{bot_username}?startgroup=true"),
        types.InlineKeyboardButton(t["btn_back"], callback_data="menu_back"),
    )
    return markup

def load_protected_words():
    if os.path.exists(PROTECTED_WORDS_FILE):
        with open(PROTECTED_WORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {int(k): set(v) for k, v in data.items()}
    return {}

def save_protected_words():
    with open(PROTECTED_WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in PROTECTED_WORDS.items()}, f, ensure_ascii=False)

def get_words(chat_id):
    return PROTECTED_WORDS.get(chat_id, set())

PROTECTED_WORDS = load_protected_words()

def links_keyboard():
    """4 أزرار شفافين تحت كل رسالة سعر"""
    markup = types.InlineKeyboardMarkup(row_width=1)
    dev = get_developer_info()
    markup.add(
        types.InlineKeyboardButton("Super Mario", url=CHANNEL_SUPER_MARIO),
        types.InlineKeyboardButton("Super Chat",  url=CHANNEL_SUPER_CHAT),
        types.InlineKeyboardButton("Ton price",   url=CHANNEL_TON_PRICE),
        types.InlineKeyboardButton(dev['name'],   url="tg://user?id=7916842400"),
    )
    return markup

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False


# ==================== /start ====================
@bot.message_handler(commands=["start"])
def start(message):
    register_user(message, notify=True)
    if message.chat.type != "private":
        register_group(message)
    not_subbed = check_force_sub(message.from_user.id)
    if not_subbed:
        bot.send_message(
            message.chat.id,
            "⚠️ *لازم تشترك في القنوات دي الأول:*",
            parse_mode="Markdown",
            reply_markup=force_sub_keyboard(not_subbed)
        )
        return
    bot.send_message(
        message.chat.id,
        "👋 أهلاً! اختار لغتك:\n🇪🇬 Arabic | 🇬🇧 English | 🇷🇺 Русский",
        reply_markup=lang_keyboard()
    )

# ==================== /admin ====================
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(
        message.chat.id,
        f"⚙️ *لوحة الأدمن*\n\n"
        f"👥 المستخدمين: {len(users)}\n"
        f"👥 الجروبات: {len(groups)}\n"
        f"📢 قنوات إجبارية: {len(force_channels)}",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

# ==================== طلبات الانضمام ====================
# ==================== ترحيب بالأعضاء الجدد ====================
@bot.chat_member_handler()
def on_chat_member_update(update):
    try:
        old = update.old_chat_member
        new = update.new_chat_member
        # دخل حد جديد (من left/kicked لـ member/administrator)
        if old.status in ["left", "kicked"] and new.status in ["member", "administrator", "restricted"]:
            member = new.user
            if member.is_bot:
                return
            name = member.first_name
            mention = f'<a href="tg://user?id={member.id}">{name}</a>'
            chat_title = update.chat.title or "الجروب"
            chat_id = update.chat.id

            welcome_text = (
                f'{ce("5472055112702629499","✨")} أهلاً وسهلاً {mention}!\n\n'
                f'{ce("5472250091332993630","🔸")} نورت <b>{chat_title}</b>\n'
                f'{ce("5472239203590888751","✅")} يسعدنا انضمامك معنا'
            )

            # جيب صورة الجروب عن طريق تحميلها فعلياً
            group_photo_bytes = None
            try:
                chat_info = bot.get_chat(chat_id)
                if chat_info.photo:
                    file_id = chat_info.photo.big_file_id
                    file_info = bot.get_file(file_id)
                    file_path = file_info.file_path
                    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        group_photo_bytes = io.BytesIO(resp.content)
                        group_photo_bytes.name = "group.jpg"
            except:
                pass

            if group_photo_bytes:
                try:
                    bot.send_photo(
                        chat_id,
                        group_photo_bytes,
                        caption=welcome_text,
                        parse_mode="HTML"
                    )
                except:
                    bot.send_message(chat_id, welcome_text, parse_mode="HTML")
            else:
                bot.send_message(chat_id, welcome_text, parse_mode="HTML")
    except:
        pass

@bot.chat_join_request_handler()
def join_request(update):
    chat_id = update.chat.id
    user_id = update.from_user.id
    name = update.from_user.first_name
    username = f"@{update.from_user.username}" if update.from_user.username else "بدون يوزر"

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"ok_{chat_id}_{user_id}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"no_{chat_id}_{user_id}")
    )
    bot.send_message(
        chat_id,
        f'<tg-emoji emoji-id="5936147649253086101">🙋‍♂️</tg-emoji> طلب انضمام جديد!\n\n'
        f'<tg-emoji emoji-id="6032608126480421344">👤</tg-emoji> العضو: {name}\n'
        f'<tg-emoji emoji-id="5873044297523140571">🆔</tg-emoji> اليوزر: {username}',
        parse_mode='HTML',
        reply_markup=markup
    )

# ==================== Callbacks ====================
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    uid = call.from_user.id
    data = call.data

    # ==================== اختيار اللغة ====================
    if data.startswith("lang_"):
        lang = data.replace("lang_", "")
        user_lang[uid] = lang
        t = LANG_TEXTS[lang]
        bot.answer_callback_query(call.id)
        caption = f'{t["welcome"]} {call.from_user.first_name}! 👋\n\n{t["main_menu_text"]}'
        # جيب صورة البوت تلقائياً
        try:
            me = bot.get_me()
            photos = bot.get_user_profile_photos(me.id, limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][0].file_id
                bot.delete_message(call.message.chat.id, call.message.message_id)
                bot.send_photo(
                    call.message.chat.id,
                    file_id,
                    caption=caption,
                    reply_markup=main_menu_keyboard(lang)
                )
            else:
                raise Exception("no photo")
        except:
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=main_menu_keyboard(lang)
            )
        return

    # ==================== القائمة الرئيسية ====================
    if data == "menu_back":
        lang = get_lang(uid)
        t = LANG_TEXTS[lang]
        bot.answer_callback_query(call.id)
        caption = f'{t["welcome"]} {call.from_user.first_name}! 👋\n\n{t["main_menu_text"]}'
        try:
            bot.edit_message_caption(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=main_menu_keyboard(lang)
            )
        except:
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=main_menu_keyboard(lang)
            )
        return

    if data == "menu_crypto":
        lang = get_lang(uid)
        t = LANG_TEXTS[lang]
        bot.answer_callback_query(call.id)
        # بعت رسالة جديدة بقايمة العملات (زي الشكل القديم بالظبط)
        bot.send_message(
            call.message.chat.id,
            f'{ce("5456543391636534278", "🔸")} <code>1 BTC</code> | <code>100 TON</code> | <code>50 TRX</code>\n'
            f'{ce("5834907543440202873", "🔸")} <code>بيتكوين</code> | <code>التون</code> | <code>تريكس</code>\n'
            f'{ce("5456543391636534278", "🔸")} <code>100 دولار</code> | <code>50 يورو</code> | <code>500 ريال</code>\n\n'
            f'{ce("5379754740798217017", "🔹")} اختار من الأزرار:',
            parse_mode="HTML",
            reply_markup=crypto_keyboard()
        )
        return

    if data == "menu_stars":
        lang = get_lang(uid)
        t = LANG_TEXTS[lang]
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t["btn_back"], callback_data="menu_back"))
        try:
            bot.edit_message_caption(
                t["stars_info"],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        except:
            bot.edit_message_text(
                t["stars_info"],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        return

    if data == "menu_groups":
        lang = get_lang(uid)
        t = LANG_TEXTS[lang]
        bot.answer_callback_query(call.id)
        try:
            bot.edit_message_caption(
                t["groups_info"],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=groups_keyboard(lang)
            )
        except:
            bot.edit_message_text(
                t["groups_info"],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=groups_keyboard(lang)
            )
        return

    if data in ["menu_cash", "menu_calc", "menu_translate", "menu_beautify"]:
        lang = get_lang(uid)
        t = LANG_TEXTS[lang]
        key_map = {
            "menu_cash":       "cash_info",
            "menu_calc":       "calc_info",
            "menu_translate":  "translate_info",
            "menu_beautify":   "beautify_info",
        }
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t["btn_back"], callback_data="menu_back"))
        # لو دوس تزيين → حط في حالة انتظار
        if data == "menu_beautify":
            admin_state[uid] = "beautify_waiting"
        bot.answer_callback_query(call.id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(t["btn_back"], callback_data="menu_back"))
        try:
            bot.edit_message_caption(
                t[key_map[data]],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        except:
            bot.edit_message_text(
                t[key_map[data]],
                call.message.chat.id,
                call.message.message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        return

    if data == "check_sub":
        not_subbed = check_force_sub(uid)
        if not_subbed:
            bot.answer_callback_query(call.id, "❌ لسه مش مشترك في كل القنوات!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ تم التحقق!", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        return

    if data.startswith("check_group_sub"):
        # استخرج الـ user_id من الـ callback
        parts = data.split("_")
        target_uid = int(parts[-1]) if parts[-1].isdigit() else 0
        # بس المستخدم المعني يقدر يدوس
        if target_uid != 0 and uid != target_uid:
            bot.answer_callback_query(call.id, "⛔ الزرار ده مش ليك!", show_alert=True)
            return
        not_subbed = check_group_force_sub(uid)
        if not_subbed:
            bot.answer_callback_query(call.id, "❌ لسه مش مشترك! اشترك الأول.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "✅ تمام! دلوقتي تقدر تستخدم البوت.", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
        return

    if data.startswith("coin_"):
        crypto_code = data.replace("coin_", "")
        loading = bot.send_message(call.message.chat.id, "⏳ جاري جلب السعر...")
        prices = get_prices()
        if not prices:
            bot.edit_message_text("❌ خطأ في الاتصال، جرب تاني!", call.message.chat.id, loading.message_id)
            bot.answer_callback_query(call.id)
            return
        result = build_crypto_result(1, crypto_code, prices)
        bot.edit_message_text(result, call.message.chat.id, loading.message_id,
                              parse_mode="HTML", reply_markup=links_keyboard())
        bot.answer_callback_query(call.id)
        return

    if data == "ok":
        pass  # handled below via split

    # طلبات القبول والرفض
    parts = data.split('_')
    if parts[0] == "ok":
        try:
            cid = int(parts[1])
            uid_member = int(parts[2])
            bot.approve_chat_join_request(cid, uid_member)
            bot.edit_message_text(
                f'<tg-emoji emoji-id="5251595639694848975">✅</tg-emoji> تم القبول بواسطة {call.from_user.first_name}',
                call.message.chat.id, call.message.message_id, parse_mode='HTML'
            )
        except: pass
        return

    if parts[0] == "no":
        try:
            bot.decline_chat_join_request(int(parts[1]), int(parts[2]))
            bot.edit_message_text(
                f'<tg-emoji emoji-id="5875100027784797000">❌</tg-emoji> تم الرفض بواسطة {call.from_user.first_name}',
                call.message.chat.id, call.message.message_id, parse_mode='HTML'
            )
        except: pass
        return

    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ مش أدمن!", show_alert=True)
        return

    if data == "admin_add_force":
        admin_state[uid] = "add_force"
        bot.answer_callback_query(call.id)
        bot.send_message(uid, "📢 أرسل يوزرنيم أو ID القناة:\n(مثال: @mychannel)")

    elif data == "admin_del_force":
        if not force_channels:
            bot.answer_callback_query(call.id, "لا توجد قنوات!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup()
        for ch_id, ch_title in force_channels.items():
            markup.add(types.InlineKeyboardButton(f"🗑 {ch_title}", callback_data=f"del_force_{ch_id}"))
        bot.answer_callback_query(call.id)
        bot.send_message(uid, "اختار القناة اللي تريد حذفها:", reply_markup=markup)

    elif data.startswith("del_force_"):
        ch_id = data.replace("del_force_", "")
        ch_title = force_channels.pop(ch_id, "القناة")
        save_json(FORCE_SUB_FILE, force_channels)
        bot.answer_callback_query(call.id, f"✅ تم حذف {ch_title}", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif data == "admin_list_force":
        bot.answer_callback_query(call.id)
        if not force_channels:
            bot.send_message(uid, "لا توجد قنوات اشتراك إجباري.")
            return
        text = f'{ce("5253495814830974755","📋")} <b>قنوات الاشتراك الإجباري:</b>\n\n'
        for ch_id, ch_title in force_channels.items():
            text += f'{ce("5456543391636534278","🔸")} {ch_title} (<code>{ch_id}</code>)\n'
        bot.send_message(uid, text, parse_mode="HTML")

    elif data == "admin_broadcast":
        admin_state[uid] = "broadcast"
        bot.answer_callback_query(call.id)
        bot.send_message(uid, "📢 أرسل الرسالة اللي تريد إذاعتها للمستخدمين:")

    elif data == "admin_stats":
        bot.answer_callback_query(call.id)
        try:
            me = bot.get_me()
            bot_name = me.first_name
            bot_username = me.username
        except:
            bot_name = "البوت"
            bot_username = "unknown"
        admin_groups_count = 0
        total_members = 0
        for gid, ginfo in groups.items():
            try:
                member = bot.get_chat_member(int(gid), me.id)
                if member.status in ["administrator", "creator"]:
                    admin_groups_count += 1
                    total_members += bot.get_chat_member_count(int(gid))
            except:
                pass
        bot.send_message(
            uid,
            f'{ce("5395587502079753683","📊")} <b>إحصائيات البوت</b>\n\n'
            f'{ce("5253510310345600737","🤖")} اسم البوت: {bot_name}\n'
            f'{ce("5873044297523140571","🔗")} يوزر: @{bot_username}\n\n'
            f'{ce("6032608126480421344","👥")} المستخدمين: <b>{len(users)}</b>\n'
            f'{ce("5933335958818114523","👥")} الجروبات: <b>{admin_groups_count}</b> جروب | الأعضاء: <b>{total_members}</b>\n\n'
            f'{ce("5379754740798217017","📅")} {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            parse_mode="HTML"
        )

    elif data == "admin_users":
        bot.answer_callback_query(call.id)
        if not users:
            bot.send_message(uid, "❌ لا يوجد مستخدمين.")
            return
        text = f"👥 <b>قائمة المستخدمين ({len(users)}):</b>\n\n"
        for i, (user_id, info) in enumerate(list(users.items())[:50], 1):
            uname = f"@{info['username']}" if info.get('username') else "—"
            text += f"{i}. {info['name']} | {uname}\n"
        if len(users) > 50:
            text += f"\n<i>... و {len(users) - 50} مستخدم آخر</i>"
        bot.send_message(uid, text, parse_mode="HTML")

# ==================== الرسائل النصية ====================
@bot.message_handler(content_types=["text"])
def handle_text(message):
    uid = message.from_user.id
    register_user(message)
    if message.chat.type != "private":
        register_group(message)

    chat_id = message.chat.id

    # أوامر الكلمات المحمية
    if message.text and message.text.strip() in ["اضافة كلمه", "اضافة كلمة", "اضافه كلمه", "اضافه كلمة"]:
        if is_admin(chat_id, uid):
            admin_state[uid] = ("add_word", chat_id)
            bot.reply_to(message, "✏️ اكتب الكلمة اللي عايز تضيفها:")
        return

    if message.text and message.text.strip() in ["حذف كلمه", "حذف كلمة"]:
        if is_admin(chat_id, uid):
            words = get_words(chat_id)
            if not words:
                bot.reply_to(message, "❌ مفيش كلمات محمية.")
            else:
                admin_state[uid] = ("del_word", chat_id)
                w = "\n".join(f"• {w}" for w in words)
                bot.reply_to(message, f"🗑 اكتب الكلمة اللي عايز تحذفها:\n\n{w}")
        return

    if message.text and message.text.strip() == "الكلمات":
        if is_admin(chat_id, uid):
            words = get_words(chat_id)
            if not words:
                bot.reply_to(message, "❌ مفيش كلمات محمية.")
            else:
                w = "\n".join(f"• {x}" for x in words)
                bot.reply_to(message, f'{ce("5197269100878907942", "📋")} الكلمات المحمية:\n\n{w}', parse_mode="HTML")
        return

    # ==================== قفل التوجيه ====================
    if message.chat.type in ["group", "supergroup"] and message.forward_date:
        if message.chat.id in group_lock_forward:
            if not is_admin(message.chat.id, uid):
                try:
                    bot.delete_message(message.chat.id, message.message_id)
                except: pass
                return

    # ==================== قفل الروابط ====================
    if message.chat.type in ["group", "supergroup"] and message.text:
        if message.chat.id in group_lock_links:
            if not is_admin(message.chat.id, uid) and re.search(r'https?://|t\.me/|www\.', message.text):
                try:
                    bot.delete_message(message.chat.id, message.message_id)
                    bot.send_message(chat_id,
                        f'{ce("5379754740798217017","🔗")} عذراً <a href="tg://user?id={uid}">{message.from_user.first_name}</a>، الروابط ممنوعة!',
                        parse_mode="HTML")
                except: pass
                return

    # ==================== أوامر الحماية ====================
    if message.chat.type in ["group", "supergroup"] and message.text and is_admin(chat_id, uid):
        cmd = message.text.strip()

        def get_target():
            # أولاً: رد على رسالة
            if message.reply_to_message and message.reply_to_message.from_user:
                return message.reply_to_message.from_user
            # ثانياً: mention entity
            if message.entities:
                for ent in message.entities:
                    if ent.type == "text_mention" and ent.user:
                        return ent.user
                    elif ent.type == "mention":
                        uname = message.text[ent.offset:ent.offset+ent.length].strip('@')
                        try:
                            return bot.get_chat_member(chat_id, "@"+uname).user
                        except:
                            pass
            return None

        if cmd.startswith("كتم"):
            target = get_target()
            if target:
                try:
                    bot.restrict_chat_member(chat_id, target.id, types.ChatPermissions(
                        can_send_messages=False, can_send_media_messages=False,
                        can_send_polls=False, can_send_other_messages=False))
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id,
                        f'{ce("5253495814830974755","🔇")} تم كتم <a href="tg://user?id={target.id}">{target.first_name}</a>',
                        parse_mode="HTML")
                except: pass
            return

        if cmd.startswith("الغاء كتم"):
            target = get_target()
            if target:
                try:
                    perms = bot.get_chat(chat_id).permissions
                    bot.restrict_chat_member(chat_id, target.id, perms)
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id,
                        f'{ce("5251595639694848975","🔊")} تم الغاء كتم <a href="tg://user?id={target.id}">{target.first_name}</a>',
                        parse_mode="HTML")
                except: pass
            return

        if cmd.startswith("طرد"):
            target = get_target()
            if target:
                try:
                    bot.ban_chat_member(chat_id, target.id)
                    if chat_id not in banned_members: banned_members[chat_id] = set()
                    banned_members[chat_id].add(target.id)
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id,
                        f'{ce("5197269100878907942","🚫")} تم طرد <a href="tg://user?id={target.id}">{target.first_name}</a> نهائياً',
                        parse_mode="HTML")
                except: pass
            return

        if cmd.startswith("الغاء طرد"):
            target = get_target()
            if target:
                try:
                    bot.unban_chat_member(chat_id, target.id)
                    if chat_id in banned_members: banned_members[chat_id].discard(target.id)
                    bot.delete_message(chat_id, message.message_id)
                    bot.send_message(chat_id,
                        f'{ce("5251595639694848975","✅")} تم الغاء طرد <a href="tg://user?id={target.id}">{target.first_name}</a>',
                        parse_mode="HTML")
                except: pass
            return

        if cmd == "قفل روابط":
            group_lock_links.add(chat_id)
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            bot.send_message(chat_id, f'{ce("5379754740798217017","🔗")} تم قفل الروابط ✅', parse_mode="HTML")
            return

        if cmd == "فتح روابط":
            group_lock_links.discard(chat_id)
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            bot.send_message(chat_id, f'{ce("5379754740798217017","🔗")} تم فتح الروابط ✅', parse_mode="HTML")
            return

        if cmd == "قفل تحويل":
            group_lock_forward.add(chat_id)
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            bot.send_message(chat_id, f'{ce("5936147649253086101","↩️")} تم قفل التوجيه ✅', parse_mode="HTML")
            return

        if cmd == "فتح تحويل":
            group_lock_forward.discard(chat_id)
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            bot.send_message(chat_id, f'{ce("5936147649253086101","↩️")} تم فتح التوجيه ✅', parse_mode="HTML")
            return

        if cmd == "مسح طرود":
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            if chat_id in banned_members and banned_members[chat_id]:
                count = len(banned_members[chat_id])
                for uid_b in list(banned_members[chat_id]):
                    try: bot.unban_chat_member(chat_id, uid_b)
                    except: pass
                banned_members[chat_id] = set()
                bot.send_message(chat_id, f'{ce("5251595639694848975","✅")} تم مسح {count} طرد', parse_mode="HTML")
            else:
                bot.send_message(chat_id, "مفيش طرود مسجلة.")
            return

    # لما الأدمن يكتب "م" → شغل المزايدة وابعت رسالة
    if message.chat.type in ["group", "supergroup"] and message.text and message.text.strip() == "م":
        try:
            member = bot.get_chat_member(chat_id, uid)
            if member.status in ["administrator", "creator"]:
                meme_mode_chats.add(chat_id)
                try:
                    bot.delete_message(chat_id, message.message_id)
                except: pass
                bot.send_message(
                    chat_id,
                    f'{ce("5472055112702629499","🔨")} <b>الجروب للمزايدة فقط</b>\n\n'
                    f'{ce("5472250091332993630","🔸")} أي رغي بيتمسح تلقائياً\n'
                    f'{ce("5472239203590888751","✅")} شارك برقمك فقط',
                    parse_mode="HTML"
                )
                return
        except: pass

    # لما الأدمن يكتب "ف" → وقف الفلتر
    if message.chat.type in ["group", "supergroup"] and message.text and message.text.strip() == "ف":
        try:
            member = bot.get_chat_member(chat_id, uid)
            if member.status in ["administrator", "creator"]:
                meme_mode_chats.discard(chat_id)
                try:
                    bot.delete_message(chat_id, message.message_id)
                except: pass
                bot.send_message(chat_id, f'{ce("5251595639694848975","✅")} الشات مفتوح، تقدروا تتكلموا!', parse_mode="HTML")
                return
        except: pass

    # فلتر المزايدة — يمسح رسايل الناس بس مش القناة
    if message.chat.type in ["group", "supergroup"] and chat_id in meme_mode_chats:
        # تجاهل رسايل القناة المرتبطة نهائياً
        if message.sender_chat:
            pass
        elif message.text and message.text.strip() in get_words(chat_id):
            pass  # كلمات محمية
        else:
            try:
                member = bot.get_chat_member(chat_id, uid)
                if member.status in ["administrator", "creator"]:
                    pass  # الأدمن يتكلم عادي
                else:
                    txt = message.text or ""
                    words = txt.split()
                    has_number = bool(re.search(r'\d', txt))
                    # لو أقل من 6 كلمات وفيها رقم → اسيبها (مزايدة عادية)
                    if has_number and len(words) <= 6:
                        pass
                    else:
                        # رغي → امسح بعد دقيقتين
                        schedule_delete(chat_id, message.message_id, delay=120)
            except: pass

    if uid in admin_state:
        step = admin_state[uid]
        if isinstance(step, tuple) and step[0] == "add_word":
            word = message.text.strip()
            cid = step[1]
            if cid not in PROTECTED_WORDS:
                PROTECTED_WORDS[cid] = set()
            PROTECTED_WORDS[cid].add(word)
            save_protected_words()
            admin_state.pop(uid, None)
            bot.reply_to(message, f'{ce("5251262487671632191", "✅")} تمت إضافة كلمة "<b>{word}</b>" للكلمات المحمية!', parse_mode="HTML")
            return
        elif isinstance(step, tuple) and step[0] == "del_word":
            word = message.text.strip()
            cid = step[1]
            if word in get_words(cid):
                PROTECTED_WORDS[cid].remove(word)
                save_protected_words()
                bot.reply_to(message, f'{ce("5251420989144725682", "✅")} تم حذف كلمة "<b>{word}</b>" من الكلمات المحمية!', parse_mode="HTML")
            else:
                bot.reply_to(message, f'❌ الكلمة "<b>{word}</b>" مش موجودة!', parse_mode="HTML")
            admin_state.pop(uid, None)
            return

    if uid == ADMIN_ID and uid in admin_state:
        step = admin_state[uid]
        if step == "add_force":
            ch = message.text.strip()
            if not ch.startswith("@") and not ch.startswith("-"):
                ch = "@" + ch
            try:
                chat_info = bot.get_chat(ch)
                force_channels[ch] = chat_info.title or ch
                save_json(FORCE_SUB_FILE, force_channels)
                bot.send_message(uid, f"✅ تم إضافة *{chat_info.title}* للاشتراك الإجباري!\n⚠️ تأكد إن البوت أدمن في القناة!", parse_mode="Markdown")
            except Exception as e:
                bot.send_message(uid, f"❌ خطأ: {e}\nتأكد إن البوت أدمن في القناة!")
            admin_state.pop(uid, None)
            return
        elif step == "broadcast":
            success, failed = 0, 0
            for user_id in users:
                try:
                    bot.copy_message(int(user_id), message.chat.id, message.message_id)
                    success += 1
                except:
                    failed += 1
            bot.send_message(uid, f"✅ تم الإرسال!\n\nنجح: {success} | فشل: {failed}")
            admin_state.pop(uid, None)
            return

        elif step == "beautify_waiting":
            raw = message.text.strip()
            lines = [l for l in raw.split('\n') if l.strip()]
            emojis = rce_list(len(lines))
            SEP = '<blockquote>' + ('—' * 15) + '</blockquote>'
            result_lines = []
            for i, line in enumerate(lines):
                result_lines.append(f'<blockquote>{emojis[i]} {line}</blockquote>')
            final = f'\n{SEP}\n'.join(result_lines)
            bot.reply_to(message, final, parse_mode="HTML")
            admin_state.pop(uid, None)
            return


    if message.text.startswith("/"): return

    text_stripped = message.text.strip()

    # ==================== معلومات المطور ====================
    if text_stripped.strip() in ["مطور", "المطور", "developer", "dev"]:
        dev = get_developer_info()
        uname = dev["username"]
        url = uname if uname.startswith("tg://") else f"https://t.me/{uname.replace('@','')}"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Super Mario", url="https://t.me/super_mairo"),
            types.InlineKeyboardButton("Super Chat",  url="https://t.me/l_z_b"),
            types.InlineKeyboardButton(dev['name'], url=f"tg://user?id=7916842400"),
        )
        text = (
            f'{ce("5253495814830974755","🤖")} <b>معلومات المطور</b>\n\n'
            f'👤 الاسم: <b>{dev["name"]}</b>\n'
            f'🔗 يوزر: {dev["username"]}\n'
            f'🆔 ID: <code>{dev["user_id"]}</code>\n'
            f'📝 {dev["bio"]}'
        )
        try:
            photos = bot.get_user_profile_photos(dev["user_id"], limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                bot.send_photo(message.chat.id, file_id, caption=text,
                               parse_mode="HTML", reply_markup=markup,
                               reply_to_message_id=message.message_id)
                return
        except: pass
        bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)
        return

    # ==================== جنرال ====================
    if text_stripped.strip().lower() in ["جنرال", "الجنرال", "general"]:
        dev = get_developer_info()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("Super Mario", url="https://t.me/super_mairo"),
            types.InlineKeyboardButton("Super Chat",  url="https://t.me/l_z_b"),
            types.InlineKeyboardButton(dev['name'],   url="tg://user?id=7916842400"),
        )
        text = (
            f'{ce("5253495814830974755","🤖")} <b>معلومات المطور</b>\n\n'
            f'👤 الاسم: <b>{dev["name"]}</b>\n'
            f'🔗 يوزر: {dev["username"]}\n'
            f'🆔 ID: <code>{dev["user_id"]}</code>\n'
            f'📝 {dev["bio"]}'
        )
        try:
            photos = bot.get_user_profile_photos(dev["user_id"], limit=1)
            if photos.total_count > 0:
                file_id = photos.photos[0][-1].file_id
                bot.send_photo(message.chat.id, file_id, caption=text,
                               parse_mode="HTML", reply_markup=markup,
                               reply_to_message_id=message.message_id)
                return
        except: pass
        bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)
        return

    # ==================== ملك الجروب ====================
    if text_stripped.strip() in ["ملك الجروب", "ملك", "king"] and message.chat.type in ["group", "supergroup"]:
        markup = types.InlineKeyboardMarkup()
        # زرار شفاف بيوديه للشات
        markup.add(types.InlineKeyboardButton(
            f"👑 {message.from_user.first_name}",
            url=f"tg://user?id={message.from_user.id}"
        ))
        mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
        bot.reply_to(
            message,
            f'👑 <b>{mention} ملك الجروب!</b>',
            parse_mode="HTML",
            reply_markup=markup
        )
        return

    if text_stripped.lower() in ["منصة", "المنصة", "منصه", "المنصه", "platform", "منصه.", "منصة."]:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("‏⬡ Fragment", url="https://fragment.com"))
        bot.reply_to(
            message,
            '<tg-emoji emoji-id="5251635900718282453">🔗</tg-emoji> <b>Web : ( https://fragment.com )</b>',
            parse_mode="HTML",
            reply_markup=markup
        )
        return

    # ==================== تحويل كاش ====================
    cash_match = re.match(r'^(\d+)\s+(01\d{9})$', text_stripped)
    if not cash_match:
        cash_match = re.match(r'^(01\d{9})\s+(\d+)$', text_stripped)
        if cash_match:
            phone, amount = cash_match.group(1), cash_match.group(2)
        else:
            phone, amount = None, None
    else:
        amount, phone = cash_match.group(1), cash_match.group(2)

    if phone and amount:
        voda_code  = f"*9*7*{phone}*{amount}#"
        orange_code = f"#7115*1*1*1*{phone}*{amount}#"
        etisalat_code = f"*777*2*{phone}*{amount}#"
        sep = "—————«•»—————"
        result = (
            f'- اضغط على كود التحويل للنسخ\n\n'
            f'<tg-emoji emoji-id="5809762661700739590">🔴</tg-emoji> <b>فودافون كاش</b>\n'
            f'<code>{voda_code}</code>\n'
            f'{sep}\n'
            f'<tg-emoji emoji-id="5809952748363324368">🟠</tg-emoji> <b>أورانج كاش</b>\n'
            f'<code>{orange_code}</code>\n'
            f'{sep}\n'
            f'<tg-emoji emoji-id="5809874352325271006">🟣</tg-emoji> <b>اتصالات كاش</b>\n'
            f'<code>{etisalat_code}</code>'
        )
        bot.reply_to(message, result, parse_mode="HTML")
        return

    # ==================== شارت العملة (تاريخ الأسعار) ====================
    chart_req = parse_chart_request(text_stripped)
    if chart_req:
        crypto_code, hours, label = chart_req
        wait_msg = bot.reply_to(message, '📊 جاري جلب البيانات...')
        try:
            result = build_price_history(crypto_code, hours, label)
            if result:
                bot.edit_message_text(result, message.chat.id, wait_msg.message_id, parse_mode="HTML")
            else:
                bot.edit_message_text("❌ مش قادر أجيب بيانات الشارت دلوقتي!", message.chat.id, wait_msg.message_id)
        except:
            try:
                bot.edit_message_text("❌ خطأ، جرب تاني!", message.chat.id, wait_msg.message_id)
            except: pass
        return

    # ==================== سعر الدولار السوق السوداء ====================
    t_low = text_stripped.lower()
    is_black_dollar = any(alias in t_low for alias in BLACK_DOLLAR_ALIASES)
    if is_black_dollar:
        result = build_black_dollar_result()
        bot.reply_to(message, result, parse_mode="HTML")
        return

    # ==================== الاقتباسات ====================
        QUOTES = [
        "النجاح ليس نهاية الفشل ليس قاتلاً، الشجاعة للاستمرار هي ما يهم. — ونستون تشرشل",
        "الطريق الوحيد للقيام بعمل رائع هو أن تحب ما تفعله. — ستيف جوبز",
        "لا تنتظر الفرصة، بل اصنعها. — جورج برنارد شو",
        "كل خبير كان مبتدئاً في يوم ما.",
        "إذا أردت أن تمشي بسرعة، امشِ وحدك. وإذا أردت أن تصل بعيداً، امشِ مع الآخرين.",
        "النجاح يأتي لمن يؤمن أن أحلامه قابلة للتحقيق.",
        "كل يوم هو فرصة جديدة لتصبح نسخة أفضل من نفسك.",
        "القوة الحقيقية ليست في العضلات بل في الإرادة.",
        "الوقت أثمن من الذهب، لا تضيعه فيما لا ينفع.",
        "من جد وجد، ومن زرع حصد.",
    ]
    if text_stripped.lower() in ["اقتباس", "quote"]:
        q = random.choice(QUOTES)
        bot.reply_to(
            message,
            f'{ce("5355052884935345861","💬")} <blockquote>{q}</blockquote>',
            parse_mode="HTML"
        )
        return

    stars_amount = parse_stars(text_stripped)
    if stars_amount is not None:
        # فحص الاشتراك الإجباري في الجروب
        if message.chat.type in ["group", "supergroup"]:
            not_subbed = check_group_force_sub(uid)
            if not_subbed:
                bot.reply_to(
                    message,
                    f'⚠️ <b>{message.from_user.first_name}</b>، لازم تشترك في القنوات دي الأول عشان تستخدم البوت:',
                    parse_mode="HTML",
                    reply_markup=group_force_sub_keyboard(not_subbed, uid)
                )
                return
        result = build_stars_result(stars_amount)
        bot.reply_to(message, result, parse_mode="HTML", reply_markup=links_keyboard())
        return

    parsed = parse_message(text_stripped)
    if not parsed: return

    temp = text_stripped.lower()
    temp = re.sub(r'[\d,\.]+', '', temp).strip()
    all_aliases = list(CRYPTO_ALIAS.keys()) + list(FIAT_ALIAS.keys())
    all_aliases.sort(key=len, reverse=True)
    for alias in all_aliases:
        temp = temp.replace(alias.lower(), '')
    temp = temp.strip()
    if temp:
        return

    # فحص الاشتراك الإجباري في الجروب
    if message.chat.type in ["group", "supergroup"]:
        not_subbed = check_group_force_sub(uid)
        if not_subbed:
            bot.reply_to(
                message,
                f'⚠️ <b>{message.from_user.first_name}</b>، لازم تشترك في القنوات دي الأول عشان تستخدم البوت:',
                parse_mode="HTML",
                reply_markup=group_force_sub_keyboard(not_subbed, uid)
            )
            return

    prices = get_prices()
    if not prices:
        bot.reply_to(message, "❌ خطأ في الاتصال، جرب تاني!")
        return

    mode, amount, code = parsed
    if mode == "crypto":
        result = build_crypto_result(amount, code, prices)
    else:
        result = build_fiat_result(amount, code, prices)
    bot.reply_to(message, result, parse_mode="HTML", reply_markup=links_keyboard())


# ==================== TON Price Tracker ====================
# ← حط هنا ID القناة لما تبعتهولي
TON_PRICE_CHANNEL = -1003549979137   # قناة @Egyptdraws

_last_ton_price = 0.0

def ton_price_tracker():
    global _last_ton_price
    print("✅ TON tracker بدأ...")
    while True:
        try:
            time.sleep(60)
            if not TON_PRICE_CHANNEL:
                print("❌ TON_PRICE_CHANNEL مش محدد")
                continue
            p = _fetch_ton_usd()
            print(f"💎 TON سعر: ${p}")
            if p <= 0:
                print("❌ السعر رجع 0")
                continue
            direction = "🟢" if p >= _last_ton_price else "🔴"
            arrow = "🚀" if p >= _last_ton_price else "💥"
            change_abs = abs(p - _last_ton_price)
            change_sign = "+" if p >= _last_ton_price else "-"
            fx = get_fx_rates()
            egp = p * fx.get("egp", EGP_PER_USD)
            msg = (
                f'💎 <b>Toncoin</b>\n'
                f'〰️〰️〰️〰️〰️〰️〰️\n'
                f'{arrow} السعر: <b>${fmt(p)}</b> {direction}\n'
                f'🇪🇬 بالجنيه: <b>{fmt(egp)}</b>\n'
                f'🔁 التغيير: <code>{change_sign}{fmt(change_abs)}$</code>\n'
                f'〰️〰️〰️〰️〰️〰️〰️\n'
                f'⏱ {datetime.utcnow().strftime("%H:%M")} UTC'
            )
            bot.send_message(TON_PRICE_CHANNEL, msg, parse_mode="HTML")
            print(f"✅ تم الإرسال للقناة")
            _last_ton_price = p
        except Exception as e:
            print(f"❌ خطأ في TON tracker: {e}")

threading.Thread(target=ton_price_tracker, daemon=True).start()

print("🚀 البوت المدمج شغال...")
bot.infinity_polling(timeout=60, long_polling_timeout=60, allowed_updates=["message","callback_query","chat_member","chat_join_request"])