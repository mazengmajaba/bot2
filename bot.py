import telebot
from telebot import types
import sqlite3
import datetime
import threading
import pytz

# ==============================================================================
# 🌟 الإعدادات الأساسية
# ==============================================================================
API_TOKEN = '8572288459:AAEeXYTjn0Euz6V419YKT15rCB-Pi2u1eFk'
ADMIN_ID = 7916842400
TARGET_CHANNEL_ID = -1001945949777
BOT_USERNAME = "ADS_MAIRO_BOT"  # يوزر بوتك بدون @

HEADER_TEXT = "#اعلان_مدفوع \n\n"

bot = telebot.TeleBot(API_TOKEN)

admin_state = {}
admin_duration_label = {}

# ==============================================================================
# 🗄️ تهيئة قاعدة البيانات
# ==============================================================================
def init_db():
    conn = sqlite3.connect('bot_management.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, join_date TEXT, is_ban INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS custom_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, btn_name TEXT, btn_text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS brokers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, username TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prices (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, duration_label TEXT, price TEXT)''')

    defaults = [('join_notify', '1')]
    for key, val in defaults:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect('bot_management.db', check_same_thread=False)

def get_setting(key):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    res = c.fetchone(); conn.close()
    return res[0] if res else '0'

def is_admin(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    return res is not None

def is_banned(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT is_ban FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone(); conn.close()
    return res[0] == 1 if res else False

def delete_ad_job(chat_id, message_id):
    try: bot.delete_message(chat_id, message_id)
    except: pass

def schedule_delete(delay_seconds, chat_id, message_id):
    t = threading.Timer(delay_seconds, delete_ad_job, args=[chat_id, message_id])
    t.daemon = True
    t.start()

# ==============================================================================
# 📋 بناء نص الأسعار ديناميكياً
# ==============================================================================
def build_prices_text(price_type):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT duration_label, price FROM prices WHERE type = ? ORDER BY id", (price_type,))
    rows = c.fetchall(); conn.close()

    if price_type == 'normal':
        title = "📦 أسعار إعلانات عرض شغلك:"
    else:
        title = "📣 أسعار الإعلانات الترويجية:\n<i>(بوت، قناة، مسابقة + تثبيت للكل)</i>"

    if not rows:
        return f"<b>{title}</b>\n\n<i>لا توجد أسعار محددة بعد.</i>"

    text = f"<b>{title}</b>\n\n"
    for label, price in rows:
        text += f"<blockquote>• {label} : {price}</blockquote>\n"
    return text

# ==============================================================================
# 🛠️ لوحات التحكم
# ==============================================================================
def main_admin_panel():
    kb = types.InlineKeyboardMarkup(row_width=2)
    join_status = "✅" if get_setting('join_notify') == '1' else "❌"
    kb.add(types.InlineKeyboardButton(f"{join_status} إشعار الدخول", callback_data="toggle_join_notify"),
           types.InlineKeyboardButton("🔄 الإذاعة", callback_data="broadcast_section"))
    kb.add(types.InlineKeyboardButton("📊 الإحصائيات", callback_data="stats_section"),
           types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user_action"))
    kb.add(types.InlineKeyboardButton("📢 نظام الإعلانات", callback_data="ads_system_panel"))
    kb.add(types.InlineKeyboardButton("💰 إدارة الأسعار", callback_data="prices_manage_panel"))
    kb.add(types.InlineKeyboardButton("👤 إضافة وسيط", callback_data="add_broker"),
           types.InlineKeyboardButton("🗑️ حذف وسيط", callback_data="del_broker"))
    kb.add(types.InlineKeyboardButton("➕ إضافة زر مخصص", callback_data="add_custom_btn"),
           types.InlineKeyboardButton("🗑️ حذف زر مخصص", callback_data="del_custom_btn"))
    kb.add(types.InlineKeyboardButton("👮 إضافة مشرف", callback_data="add_new_admin"),
           types.InlineKeyboardButton("👥 قائمة المشرفين", callback_data="list_admins"))
    return kb

def sub_admin_panel():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📢 نظام الإعلانات", callback_data="ads_system_panel"))
    return kb

def user_main_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💸 عمل إعلان", callback_data="get_contact"),
        types.InlineKeyboardButton("📝 أسعار الإعلانات", callback_data="get_prices")
    )
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT btn_name FROM custom_buttons")
    for btn in c.fetchall():
        kb.add(types.InlineKeyboardButton(btn[0], callback_data=f"cbtn_{btn[0]}"))
    conn.close()
    return kb

def prices_type_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📦 إعلانات عرض شغلك", callback_data="prices_normal"),
        types.InlineKeyboardButton("📣 إعلانات ترويجية", callback_data="prices_promo")
    )
    kb.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main"))
    return kb

def brokers_keyboard():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, name, username FROM brokers")
    brokers = c.fetchall(); conn.close()
    kb = types.InlineKeyboardMarkup(row_width=2)
    for b in brokers:
        kb.add(types.InlineKeyboardButton(f"👤 {b[1]}", callback_data=f"select_broker_{b[0]}"))
    kb.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main"))
    return kb

def channel_ad_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("↗️ لعمل اعلان مدفوع", url=f"https://t.me/{BOT_USERNAME}"))
    return kb

def prices_manage_panel_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📦 أسعار عرض شغلك", callback_data="manage_normal_prices"),
        types.InlineKeyboardButton("📣 أسعار الترويجية", callback_data="manage_promo_prices")
    )
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    return kb

def manage_prices_keyboard(price_type):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, duration_label, price FROM prices WHERE type = ? ORDER BY id", (price_type,))
    rows = c.fetchall(); conn.close()
    kb = types.InlineKeyboardMarkup(row_width=1)
    for row in rows:
        kb.add(types.InlineKeyboardButton(f"❌ {row[1]} : {row[2]}", callback_data=f"del_price_{row[0]}"))
    kb.add(types.InlineKeyboardButton("➕ إضافة سعر جديد", callback_data=f"add_price_{price_type}"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع لإدارة الأسعار", callback_data="prices_manage_panel"))
    return kb

# ==============================================================================
# 🚀 المعالجة
# ==============================================================================
WELCOME_TEXT = (
    "✨ أهلاً بك في بوت الإعلانات المدفوعة ✨\n\n"
    "<blockquote>• اعمل إعلانك بسهولة عبر وسيط معتمد.</blockquote>\n"
    "<blockquote>• مراجعة الإعلان وتحديد مدة النشر يدوياً.</blockquote>\n"
    "<blockquote>• الحذف تلقائي بعد انتهاء المدة.</blockquote>"
)

@bot.message_handler(commands=['start', 'admin'])
def handle_commands(message):
    uid = message.from_user.id
    if is_banned(uid): return

    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not c.fetchone():
        username = f"@{message.from_user.username}" if message.from_user.username else "لا يوجد"
        c.execute("INSERT INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)",
                  (uid, username, message.from_user.first_name, datetime.datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        if get_setting('join_notify') == '1':
            c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
            bot.send_message(ADMIN_ID, f"👾 دخول عضو جديد:\nالاسم: {message.from_user.first_name}\nالايدي: `{uid}`\nالمجموع: {total}", parse_mode="Markdown")
    conn.close()

    if uid == ADMIN_ID:
        bot.send_message(message.chat.id, "🛠️ لوحة التحكم الكاملة:", reply_markup=main_admin_panel())
    elif is_admin(uid):
        bot.send_message(message.chat.id, "📢 مرحباً، يمكنك نشر الإعلانات من هنا:", reply_markup=sub_admin_panel())
    else:
        bot.send_message(message.chat.id, WELCOME_TEXT, parse_mode="HTML", reply_markup=user_main_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid, mid = call.from_user.id, call.message.message_id
    if is_banned(uid): return

    # أزرار مخصصة
    if call.data.startswith("cbtn_"):
        name = call.data.replace("cbtn_", "")
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT btn_text FROM custom_buttons WHERE btn_name = ?", (name,))
        res = c.fetchone(); conn.close()
        if res: bot.send_message(uid, res[0])
        bot.answer_callback_query(call.id)
        return

    # اختيار وسيط
    if call.data.startswith("select_broker_"):
        broker_id = int(call.data.replace("select_broker_", ""))
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT name, username FROM brokers WHERE id = ?", (broker_id,))
        res = c.fetchone(); conn.close()
        if res:
            name, username = res
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💳 تواصل معه", url=f"https://t.me/{username.replace('@', '')}"))
            kb.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="get_contact"))
            bot.edit_message_text(
                "✅ تم اختيار الوسيط.\n\n<blockquote>راسل الوسيط للدفع وترتيب نشر إعلانك.</blockquote>",
                uid, mid, parse_mode="HTML", reply_markup=kb
            )
        bot.answer_callback_query(call.id)
        return

    # ========== مستخدم عادي ==========
    if not is_admin(uid):
        if call.data == "get_prices":
            bot.edit_message_text("📝 اختر نوع الإعلان لعرض أسعاره:", uid, mid, reply_markup=prices_type_keyboard())

        elif call.data == "prices_normal":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 رجوع للأسعار", callback_data="get_prices"))
            kb.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main"))
            bot.edit_message_text(build_prices_text('normal'), uid, mid, parse_mode="HTML", reply_markup=kb)

        elif call.data == "prices_promo":
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔙 رجوع للأسعار", callback_data="get_prices"))
            kb.add(types.InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main"))
            bot.edit_message_text(build_prices_text('promo'), uid, mid, parse_mode="HTML", reply_markup=kb)

        elif call.data == "back_to_main":
            bot.edit_message_text(WELCOME_TEXT, uid, mid, parse_mode="HTML", reply_markup=user_main_keyboard())

        elif call.data == "get_contact":
            conn = get_db(); c = conn.cursor()
            c.execute("SELECT id FROM brokers")
            brokers = c.fetchall(); conn.close()
            if not brokers:
                bot.answer_callback_query(call.id, "⚠️ لا يوجد وسطاء متاحين حالياً.", show_alert=True)
            elif len(brokers) == 1:
                conn2 = get_db(); c2 = conn2.cursor()
                c2.execute("SELECT name, username FROM brokers WHERE id = ?", (brokers[0][0],))
                res = c2.fetchone(); conn2.close()
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("💳 تواصل معه", url=f"https://t.me/{res[1].replace('@', '')}"))
                kb.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main"))
                bot.edit_message_text(
                    "✅ تم اختيار الوسيط.\n\n<blockquote>راسل الوسيط للدفع وترتيب نشر إعلانك.</blockquote>",
                    uid, mid, parse_mode="HTML", reply_markup=kb
                )
            else:
                bot.edit_message_text("👤 اختر الوسيط المناسب للدفع:", uid, mid, reply_markup=brokers_keyboard())

        bot.answer_callback_query(call.id)
        return

    # ========== نظام الإعلانات - للمشرفين كلهم ==========
    if call.data == "ads_system_panel":
        kb = types.InlineKeyboardMarkup(row_width=2)
        durations = [
            ("30 دقيقة 🕐", 1800),
            ("1 ساعة 🕑", 3600),
            ("2 ساعة 🕒", 7200),
            ("3 ساعات 🕓", 10800),
            ("4 ساعات 🕔", 14400),
            ("5 ساعات 🕔", 18000),
            ("6 ساعات 🕕", 21600),
            ("7 ساعات 🕖", 25200),
            ("8 ساعات 🕗", 28800),
            ("9 ساعات 🕘", 32400),
            ("24 ساعة 🕙", 86400),
            ("48 ساعة 🕚", 172800),
        ]
        for t, s in durations:
            kb.add(types.InlineKeyboardButton(t, callback_data=f"sch_{s}_{t}"))
        back_cb = "main_menu" if uid == ADMIN_ID else "sub_menu"
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=back_cb))
        bot.edit_message_text("⏰ اختر مدة الإعلان قبل الحذف التلقائي:", uid, mid, reply_markup=kb)

    elif call.data == "sub_menu":
        bot.edit_message_text("📢 مرحباً، يمكنك نشر الإعلانات من هنا:", uid, mid, reply_markup=sub_admin_panel())

    elif call.data.startswith("sch_"):
        parts = call.data.split('_', 2)
        admin_state[uid] = int(parts[1])
        admin_duration_label[uid] = parts[2]
        bot.send_message(uid, "📤 أرسل الإعلان الآن (نص، صورة، أو فيديو):")

    # ========== باقي الأوامر للمالك فقط ==========
    elif uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ ليس لديك صلاحية.", show_alert=True)
        return

    elif call.data == "prices_manage_panel":
        bot.edit_message_text("💰 إدارة الأسعار - اختر نوع الإعلان:", uid, mid, reply_markup=prices_manage_panel_kb())

    elif call.data == "manage_normal_prices":
        bot.edit_message_text("📦 أسعار عرض شغلك:\n\nاضغط ❌ لحذف أو ➕ لإضافة سعر.", uid, mid, reply_markup=manage_prices_keyboard('normal'))

    elif call.data == "manage_promo_prices":
        bot.edit_message_text("📣 أسعار الإعلانات الترويجية:\n\nاضغط ❌ لحذف أو ➕ لإضافة سعر.", uid, mid, reply_markup=manage_prices_keyboard('promo'))

    elif call.data.startswith("add_price_"):
        price_type = call.data.replace("add_price_", "")
        type_name = "عرض شغلك" if price_type == 'normal' else "ترويجية"
        msg = bot.send_message(uid, f"✏️ أرسل السعر الجديد ({type_name}) بالشكل ده:\n\n<b>المدة : السعر</b>\n\nمثال:\n1 ساعة : 15 جنيه", parse_mode="HTML")
        bot.register_next_step_handler(msg, save_price, price_type)

    elif call.data.startswith("del_price_"):
        price_id = int(call.data.replace("del_price_", ""))
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT type FROM prices WHERE id = ?", (price_id,))
        res = c.fetchone()
        c.execute("DELETE FROM prices WHERE id = ?", (price_id,))
        conn.commit(); conn.close()
        price_type = res[0] if res else 'normal'
        panel_name = "📦 أسعار عرض شغلك" if price_type == 'normal' else "📣 أسعار الإعلانات الترويجية"
        bot.edit_message_text(f"✅ تم الحذف.\n\n{panel_name}:\n\nاضغط ❌ لحذف أو ➕ لإضافة سعر.", uid, mid, reply_markup=manage_prices_keyboard(price_type))

    elif call.data == "add_broker":
        msg = bot.send_message(uid, "👤 أرسل اسم الوسيط:")
        bot.register_next_step_handler(msg, process_broker_name)

    elif call.data == "del_broker":
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT id, name, username FROM brokers"); brokers = c.fetchall(); conn.close()
        if not brokers:
            bot.answer_callback_query(call.id, "لا يوجد وسطاء لحذفهم.")
            return
        kb = types.InlineKeyboardMarkup()
        for b in brokers:
            kb.add(types.InlineKeyboardButton(f"❌ {b[1]} ({b[2]})", callback_data=f"confirm_del_broker_{b[0]}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        bot.edit_message_text("اختر الوسيط لحذفه:", uid, mid, reply_markup=kb)

    elif call.data.startswith("confirm_del_broker_"):
        broker_id = int(call.data.replace("confirm_del_broker_", ""))
        conn = get_db(); c = conn.cursor()
        c.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
        conn.commit(); conn.close()
        bot.edit_message_text("✅ تم حذف الوسيط بنجاح.", uid, mid, reply_markup=main_admin_panel())

    elif call.data == "toggle_join_notify":
        cur = get_setting('join_notify'); new = '0' if cur == '1' else '1'
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = ?", (new, 'join_notify'))
        conn.commit(); conn.close()
        bot.edit_message_reply_markup(uid, mid, reply_markup=main_admin_panel())

    elif call.data == "add_custom_btn":
        msg = bot.send_message(uid, "✏️ أرسل اسم الزر الجديد:")
        bot.register_next_step_handler(msg, process_btn_name)

    elif call.data == "del_custom_btn":
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT btn_name FROM custom_buttons"); btns = c.fetchall(); conn.close()
        if not btns: return bot.answer_callback_query(call.id, "لا توجد أزرار لحذفها")
        kb = types.InlineKeyboardMarkup()
        for b in btns: kb.add(types.InlineKeyboardButton(f"❌ {b[0]}", callback_data=f"dlb_{b[0]}"))
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        bot.edit_message_text("اختر الزر للحذف:", uid, mid, reply_markup=kb)

    elif call.data.startswith("dlb_"):
        name = call.data.replace("dlb_", "")
        conn = get_db(); c = conn.cursor()
        c.execute("DELETE FROM custom_buttons WHERE btn_name = ?", (name,))
        conn.commit(); conn.close()
        bot.edit_message_text("✅ تم حذف الزر.", uid, mid, reply_markup=main_admin_panel())

    elif call.data == "main_menu":
        bot.edit_message_text("🛠️ لوحة التحكم الكاملة:", uid, mid, reply_markup=main_admin_panel())

    elif call.data == "broadcast_section":
        msg = bot.send_message(uid, "📢 أرسل رسالة الإذاعة:")
        bot.register_next_step_handler(msg, run_broadcast)

    elif call.data == "stats_section":
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users"); tot = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_ban = 1"); ban = c.fetchone()[0]; conn.close()
        bot.edit_message_text(
            f"📊 الإحصائيات:\n👥 الأعضاء: {tot}\n🚫 المحظورين: {ban}",
            uid, mid,
            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        )

    elif call.data == "add_new_admin":
        msg = bot.send_message(uid, "👮 أرسل يوزر المشرف الجديد (بالـ @):")
        bot.register_next_step_handler(msg, save_admin_by_username)

    elif call.data == "list_admins":
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT user_id FROM admins"); admins = c.fetchall(); conn.close()
        admin_list = "👮 قائمة المشرفين الحالية:\n\n"
        for adm in admins: admin_list += f"• `{adm[0]}`\n"
        bot.send_message(uid, admin_list, parse_mode="Markdown")

    elif call.data == "ban_user_action":
        msg = bot.send_message(uid, "🚫 أرسل يوزر أو ID المستخدم لحظره:")
        bot.register_next_step_handler(msg, ban_user)

    bot.answer_callback_query(call.id)

# ==============================================================================
# 📝 الدوال المساعدة
# ==============================================================================
def process_broker_name(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, f"✅ الاسم: {name}\n\n👤 أرسل الآن يوزر الوسيط (بالـ @):")
    bot.register_next_step_handler(msg, save_broker, name)

def save_broker(message, name):
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO brokers (name, username) VALUES (?, ?)", (name, username))
    conn.commit(); conn.close()
    bot.send_message(message.chat.id, f"✅ تم إضافة الوسيط بنجاح!\nالاسم: {name}\nاليوزر: {username}")

def save_price(message, price_type):
    text = message.text.strip()
    if ':' not in text:
        bot.send_message(message.chat.id, "❌ الشكل غير صحيح. أرسل مثلاً:\n1 ساعة : 15 جنيه")
        return
    parts = text.split(':', 1)
    duration_label = parts[0].strip()
    price = parts[1].strip()
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO prices (type, duration_label, price) VALUES (?, ?, ?)", (price_type, duration_label, price))
    conn.commit(); conn.close()
    type_name = "عرض شغلك" if price_type == 'normal' else "ترويجية"
    bot.send_message(message.chat.id, f"✅ تم إضافة السعر!\n{duration_label} : {price}\n(نوع: {type_name})")

def ban_user(message):
    target = message.text.strip()
    conn = get_db(); c = conn.cursor()
    if target.startswith("@"):
        c.execute("SELECT user_id FROM users WHERE username = ?", (target,))
    else:
        try:
            c.execute("SELECT user_id FROM users WHERE user_id = ?", (int(target),))
        except:
            bot.send_message(message.chat.id, "❌ يوزر أو ID غير صحيح."); conn.close(); return
    res = c.fetchone()
    if res:
        c.execute("UPDATE users SET is_ban = 1 WHERE user_id = ?", (res[0],))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم حظر {target} بنجاح.")
    else:
        bot.send_message(message.chat.id, "❌ المستخدم غير موجود في قاعدة البيانات.")
    conn.close()

def save_admin_by_username(message):
    username = message.text.strip()
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE username = ?", (username,))
    res = c.fetchone()
    if res:
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (res[0],))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم رفع {username} مشرف بنجاح.")
    else:
        bot.send_message(message.chat.id, "❌ الشخص غير مسجل، يجب أن يرسل /start أولاً.")
    conn.close()

def process_btn_name(message):
    name = message.text
    msg = bot.send_message(message.chat.id, f"✅ تم اختيار اسم [{name}]\n✏️ أرسل الآن المحتوى الذي سيبعثه البوت عند الضغط:")
    bot.register_next_step_handler(msg, save_btn, name)

def save_btn(message, name):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO custom_buttons (btn_name, btn_text) VALUES (?, ?)", (name, message.text))
    conn.commit(); conn.close()
    bot.send_message(message.chat.id, "✅ تم إضافة الزر بنجاح.")

def run_broadcast(message):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); conn.close()
    count = 0
    for u in users:
        try: bot.copy_message(u[0], message.chat.id, message.message_id); count += 1
        except: continue
    bot.send_message(message.chat.id, f"✅ تمت الإذاعة لـ {count} عضو.")

@bot.message_handler(content_types=['text', 'photo', 'video'], func=lambda m: m.from_user.id in admin_state)
def process_ad(message):
    if not is_admin(message.from_user.id): return
    duration = admin_state.pop(message.from_user.id)
    label = admin_duration_label.pop(message.from_user.id, "غير محدد")

    raw_text = (message.text if message.text else message.caption if message.caption else "")
    safe_text = raw_text.replace('<', '&lt;').replace('>', '&gt;')

    final_text = (
        f"<b>{HEADER_TEXT}</b>"
        f"{safe_text}\n\n"
        f"<blockquote>📢 الإعلان مجرد إعلان، ولا نضمن أي جهة معلن عنها.</blockquote>\n\n"
        f"⏱️ <b>مدة الإعلان:</b> {label}"
    )

    try:
        sent = None
        if message.content_type == 'text':
            sent = bot.send_message(TARGET_CHANNEL_ID, final_text, parse_mode="HTML", reply_markup=channel_ad_keyboard())
        elif message.content_type == 'photo':
            sent = bot.send_photo(TARGET_CHANNEL_ID, message.photo[-1].file_id, caption=final_text, parse_mode="HTML", reply_markup=channel_ad_keyboard())
        elif message.content_type == 'video':
            sent = bot.send_video(TARGET_CHANNEL_ID, message.video.file_id, caption=final_text, parse_mode="HTML", reply_markup=channel_ad_keyboard())

        if sent:
            schedule_delete(duration, TARGET_CHANNEL_ID, sent.message_id)
            bot.reply_to(message, f"🚀 تم نشر الإعلان بنجاح لمدة ({label}) وجدولة الحذف التلقائي ✅")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطأ في النشر: {e}")

bot.infinity_polling()
