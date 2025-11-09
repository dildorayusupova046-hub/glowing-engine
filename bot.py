# main.py
# Pydroid3 / Python (telebot) single-file bot
# Requirements:
# pip install pyTelegramBotAPI

import telebot
from telebot import types
import json
import os
import time
import random
from datetime import datetime
import threading

# ---------------- CONFIG ----------------
TOKEN = "8445356797:AAEpXGCkz3MgkzDdpX4ElJhzKsRPGjVr_k8"
CHANNEL_USERNAME = "@Aviator_Bashoratchi"
ADMIN_CHANNEL_ID = -1002952868625
ADMIN_USER_ID = 5747707145
GAME_URL = "https://1wlshx.life/v3/aggressive-casino?p=3g2i&sub1=5747707145"
DATA_FILE = "data.json"
MIN_WITHDRAW = 120000
REF_BONUS = 1500
# ----------------------------------------

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# thread-safe lock for data file access
data_lock = threading.Lock()

# ---------- Data helpers ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "withdraws": {}, "next_withdraw_id": 1}
    try:
        with data_lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("load_data error:", e)
        return {"users": {}, "withdraws": {}, "next_withdraw_id": 1}

def save_data(d):
    try:
        with data_lock:
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            os.replace(tmp, DATA_FILE)
    except Exception as e:
        print("save_data error:", e)

data = load_data()

def ensure_user_obj(user):
    uid = str(user.id)
    changed = False
    if uid not in data["users"]:
        data["users"][uid] = {
            "id": user.id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "balance": 0,
            "refs": [],        # list of invited user ids
            "referred_by": None
        }
        changed = True
    else:
        # update username/first name if changed
        u = data["users"][uid]
        if (user.username or "") != u.get("username"):
            u["username"] = user.username or ""
            changed = True
        if (user.first_name or "") != u.get("first_name"):
            u["first_name"] = user.first_name or ""
            changed = True
    if changed:
        save_data(data)
    return data["users"][uid]

def human(n):
    try:
        return f"{int(n):,}"
    except:
        return str(n)

# ---------- keyboards ----------
def main_keyboard(is_admin=False):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🎯 Signal", "🔗 Referal tizimi")
    kb.add("💸 Pulni yechish", "ℹ️ Bot haqida")
    kb.add("⏳ Tez orada")
    if is_admin:
        kb.add("🛠️ Admin panel")
    return kb

def sub_check_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🔔 Kanalga obuna bo'lish")
    kb.add("✅ Tekshirish")
    return kb

def admin_panel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👥 Foydalanuvchilar soni", "📣 Hammaga xabar yuborish")
    kb.add("✉️ Yakka xabar (ID)", "📥 Yechish so'rovlarini ko'rish")
    kb.add("✅ To'lov bajarildi", "🔙 Orqaga")
    return kb

# ---------- subscription check ----------
def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("creator", "administrator", "member")
    except Exception as e:
        # print("subscription check error:", e)
        return False

# ---------- signal generator ----------
def generate_grid():
    # 5x5 grid, place 1-4 stars randomly
    total = 25
    stars = random.randint(1, 4)
    pos = set(random.sample(range(total), stars))
    s = ""
    for i in range(total):
        s += "⭐ " if i in pos else "⬛ "
        if (i+1) % 5 == 0:
            s += "\n"
    return s.strip()

# ---------- /start ----------
@bot.message_handler(commands=['start'])
def start_cmd(m):
    user = m.from_user
    ensure_user_obj(user)
    # handle referral param: can be "/start <ref>" or "/start=xxx" (some clients)
    parts = (m.text or "").replace("\u00A0", " ").split()
    ref_id = None
    try:
        if len(parts) >= 2:
            ref = parts[1]
            if ref.startswith("start="):
                ref = ref.split("=",1)[1]
            if ref.isdigit():
                ref_id = int(ref)
        else:
            # also handle "/start=123" without space
            if "=" in (m.text or ""):
                after = (m.text or "").split("=",1)[1]
                if after.isdigit():
                    ref_id = int(after)
    except:
        ref_id = None

    if ref_id and ref_id != user.id:
        u = data["users"].get(str(user.id))
        if u and not u.get("referred_by"):
            # ensure ref exists
            if str(ref_id) not in data["users"]:
                data["users"][str(ref_id)] = {"id": ref_id, "username": "", "first_name": "", "balance": 0, "refs": [], "referred_by": None}
            u["referred_by"] = ref_id
            data["users"][str(ref_id)].setdefault("refs", []).append(user.id)
            data["users"][str(ref_id)]["balance"] = data["users"][str(ref_id)].get("balance",0) + REF_BONUS
            save_data(data)
            # notify referrer (if possible)
            try:
                bot.send_message(ref_id, f"🎉 Siz yangi do'stni taklif qildingiz! +{human(REF_BONUS)} so'm sizning balansingizga qo'shildi.")
            except:
                pass

    # check subscription
    if not is_subscribed(user.id):
        bot.send_message(user.id, "🔔 Botdan foydalanish uchun avval kanalga obuna bo'ling:", reply_markup=sub_check_keyboard())
        return

    # if admin show admin button
    is_admin = (user.id == ADMIN_USER_ID)
    bot.send_message(user.id, f"👋 Salom, {user.first_name}!\nQuyidagilardan birini tanlang:", reply_markup=main_keyboard(is_admin))

# ---------- reply handlers ----------
@bot.message_handler(func=lambda m: True)
def reply_router(m):
    text = (m.text or "").strip()
    user = m.from_user
    ensure_user_obj(user)

    # Subscription help
    if text == "🔔 Kanalga obuna bo'lish":
        bot.send_message(user.id, f"🔔 Kanalga obuna bo'ling: {CHANNEL_USERNAME}\nSo'ngra '✅ Tekshirish' tugmasini bosing.")
        return
    if text == "✅ Tekshirish":
        if is_subscribed(user.id):
            is_admin = (user.id == ADMIN_USER_ID)
            bot.send_message(user.id, "✅ Obuna tasdiqlandi. Menyu ochildi.", reply_markup=main_keyboard(is_admin))
        else:
            bot.send_message(user.id, "❌ Siz hali kanalga obuna bo'lmagansiz. Iltimos kanalga a'zo bo'ling va qayta tekshiring.")
        return

    # MAIN MENU OPTIONS
    if text == "🎯 Signal":
        if not is_subscribed(user.id):
            bot.send_message(user.id, "🔔 Avval kanalga obuna bo'ling.", reply_markup=sub_check_keyboard())
            return
        grid = generate_grid()
        now = datetime.now().strftime("%H:%M")
        txt = (f"🎯 MINES SIGNAL\n\n"
               f"🕒 {now} — signal 5 daqiqa amal qiladi\n\n"
               f"{grid}\n\n"
               f"▶️ O'yinni boshlash: {GAME_URL}\n\n"
               f"⚠️ Eslatma: signal faqat tavsiya, o'yin xavfli va zarar ko'rishingiz mumkin.")
        # include link button under message
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("▶️ O'yinni boshlash", url=GAME_URL))
        bot.send_message(user.id, txt, reply_markup=kb)
        return

    if text == "🔗 Referal tizimi":
        u = data["users"].get(str(user.id), {})
        try:
            me = bot.get_me().username
            ref_link = f"https://t.me/{me}?start={user.id}"
        except:
            ref_link = f"t.me/{bot.get_me().username}?start={user.id}"
        bot.send_message(user.id,
                         f"🔗 Sizning referal havolangiz:\n{ref_link}\n\n"
                         f"🎁 Har bir do'st uchun: +{human(REF_BONUS)} so'm\n"
                         f"💰 Balans: {human(u.get('balance',0))} so'm\n"
                         f"👥 Chaqqanlar soni: {len(u.get('refs',[]))}\n\n"
                         f"💸 Pulni yechish uchun '💸 Pulni yechish' tugmasini bosing.")
        return

    if text == "💸 Pulni yechish":
        u = data["users"].get(str(user.id), {})
        bal = u.get("balance", 0)
        if bal < MIN_WITHDRAW:
            bot.send_message(user.id, f"❌ Sizda yetarli mablag' yo'q.\nMinimal yechish: {human(MIN_WITHDRAW)} so'm\nSizda: {human(bal)} so'm")
            return
        msg = bot.send_message(user.id, f"💸 Sizning balans: {human(bal)} so'm\nIltimos, yechmoqchi bo'lgan miqdorni faqat raqam ko'rinishida kiriting (masalan: 120000).")
        bot.register_next_step_handler(msg, process_withdraw_amount)
        return

    if text == "ℹ️ Bot haqida":
        bot.send_message(user.id,
                         "🤖 UpMines — AI MINES SIGNAL BOT\n\n"
                         "• Sun'iy intellekt asosida signallar.\n"
                         "• Referal orqali pul yig'ing.\n"
                         "• To'lovlar admin tomonidan tekshiriladi (24 soat ichida amalga oshirilishi mumkin).\n\n"
                         "Omad sizga yor bo'lsin!")
        return

    if text == "⏳ Tez orada":
        bot.send_message(user.id, "⏳ Tez orada mukammal Aviator bot tayyor bo'ladi. Yangiliklar kanalida kuzatib boring.")
        return

    # Admin panel (reply button)
    if text == "🛠️ Admin panel" or (text.lower() == "/admin"):
        if user.id != ADMIN_USER_ID:
            bot.send_message(user.id, "❌ Siz admin emassiz.")
            return
        bot.send_message(user.id, "🛠️ Admin panel ochildi:", reply_markup=admin_panel_keyboard())
        return

    # Admin actions (reply buttons)
    if text == "👥 Foydalanuvchilar soni":
        if user.id != ADMIN_USER_ID: return
        total = len(data.get("users", {}))
        total_balance = sum(u.get("balance",0) for u in data.get("users", {}).values())
        bot.send_message(user.id, f"👥 Foydalanuvchilar: {total}\n💰 Umumiy balans: {human(total_balance)} so'm")
        return

    if text == "📣 Hammaga xabar yuborish":
        if user.id != ADMIN_USER_ID: return
        msg = bot.send_message(user.id, "✏️ Iltimos, hammaga yuboriladigan matnni yuboring:")
        bot.register_next_step_handler(msg, broadcast_all)
        return

    if text == "✉️ Yakka xabar (ID)":
        if user.id != ADMIN_USER_ID: return
        msg = bot.send_message(user.id, "✉️ Iltimos, user ID sini yuboring:")
        bot.register_next_step_handler(msg, ask_admin_message_userid)
        return

    if text == "📥 Yechish so'rovlarini ko'rish":
        if user.id != ADMIN_USER_ID: return
        withdraws = data.get("withdraws", {})
        out = []
        for wid, w in withdraws.items():
            out.append(f"ID:{wid} UID:{w['user_id']} @{w.get('username','')} Sum:{human(w['amount'])} Status:{w['status']}")
        bot.send_message(user.id, "📥 Withdraw so'rovlari:\n" + ("\n".join(out) if out else "Hozircha so'rovlar yo'q."))
        return

    if text == "✅ To'lov bajarildi":
        if user.id != ADMIN_USER_ID: return
        msg = bot.send_message(user.id, "✅ Iltimos tasdiqlamoqchi bo'lgan Withdraw ID sini kiriting:")
        bot.register_next_step_handler(msg, admin_confirm_withdraw)
        return

    if text == "🔙 Orqaga":
        is_admin = (user.id == ADMIN_USER_ID)
        bot.send_message(user.id, "🔙 Orqaga qaytdi.", reply_markup=main_keyboard(is_admin))
        return

    # default
    bot.send_message(user.id, "Iltimos, pastdagi menyulardan birini tanlang.", reply_markup=main_keyboard(user.id==ADMIN_USER_ID))

# ---------- withdraw flow ----------
def process_withdraw_amount(message):
    user = message.from_user
    txt = (message.text or "").strip().replace(" ", "")
    if not txt.isdigit():
        msg = bot.send_message(user.id, "❌ Iltimos faqat raqam kiriting (miqdor). Qayta urin.")
        bot.register_next_step_handler(msg, process_withdraw_amount)
        return
    amount = int(txt)
    u = data["users"].get(str(user.id), {})
    bal = u.get("balance", 0)
    if amount < MIN_WITHDRAW:
        msg = bot.send_message(user.id, f"❌ Minimal yechish: {human(MIN_WITHDRAW)} so'm. Qayta urin.")
        bot.register_next_step_handler(msg, process_withdraw_amount)
        return
    if amount > bal:
        bot.send_message(user.id, f"❌ Sizda yetarli mablag' yo'q. Balans: {human(bal)} so'm")
        return
    # ask for card
    msg = bot.send_message(user.id, "💳 Iltimos karta raqamini yuboring (masalan: 8600xxxxxxxxxxxx):")
    # store temporary pending amount in user record
    data["users"][str(user.id)]["pending_withdraw_amount"] = amount
    save_data(data)
    bot.register_next_step_handler(msg, finalize_withdraw)

def finalize_withdraw(message):
    user = message.from_user
    card = (message.text or "").strip()
    uid = str(user.id)
    urec = data["users"].get(uid)
    amount = urec.pop("pending_withdraw_amount", None) if urec else None
    if amount is None:
        bot.send_message(user.id, "❌ So'rov topilmadi. Iltimos qayta urin.")
        return
    # basic card validation
    if len(card) < 6 or not any(ch.isdigit() for ch in card):
        bot.send_message(user.id, "❌ Karta raqami noto'g'ri. Qayta urin.")
        # restore pending so user can retry
        urec["pending_withdraw_amount"] = amount
        save_data(data)
        msg = bot.send_message(user.id, "💳 Iltimos to'g'ri karta raqamini yuboring:")
        bot.register_next_step_handler(msg, finalize_withdraw)
        return
    # create withdraw record
    wid = str(data.get("next_withdraw_id",1))
    data["withdraws"][wid] = {
        "id": wid,
        "user_id": user.id,
        "username": user.username or "",
        "amount": amount,
        "card": card,
        "status": "pending",
        "time": datetime.now().isoformat()
    }
    data["next_withdraw_id"] = int(wid) + 1
    save_data(data)
    # notify user
    bot.send_message(user.id, "✅ So'rovingiz qabul qilindi. To'lovlar 24 soat ichida amalga oshirilishi mumkin. Operator siz bilan bog'lanadi.")
    # notify admin channel with inline approve button
    admin_text = (f"💸 Yangi yechish so'rovi!\n\nUser: @{user.username or user.first_name}\n"
                  f"ID: {user.id}\nSumma: {human(amount)} so'm\nKarta: {card}\nVaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nWithdraw ID: {wid}")
    try:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ To'lov bajarildi (admin)", callback_data=f"pay:{wid}"))
        bot.send_message(ADMIN_CHANNEL_ID, admin_text, reply_markup=kb)
    except Exception as e:
        # fallback: if sending to admin channel fails, DM to admin user
        try:
            bot.send_message(ADMIN_USER_ID, admin_text)
        except:
            print("admin notify failed:", e)
    return

# Admin callback from admin channel
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("pay:"))
def admin_pay_callback(call):
    # Only admin user allowed to press
    try:
        if call.from_user.id != ADMIN_USER_ID:
            bot.answer_callback_query(call.id, "Siz bu amalni bajara olmaysiz.")
            return
        _, wid = call.data.split(":")
        w = data["withdraws"].get(wid)
        if not w:
            bot.answer_callback_query(call.id, "So'rov topilmadi.")
            return
        if w["status"] == "paid":
            bot.answer_callback_query(call.id, "Oldin tasdiqlangan.")
            return
        # mark paid
        w["status"] = "paid"
        save_data(data)
        # decrease user balance (if not yet decreased)
        uid = str(w["user_id"])
        if uid in data["users"]:
            data["users"][uid]["balance"] = max(0, data["users"][uid].get("balance",0) - w["amount"])
            save_data(data)
        # notify user
        try:
            bot.send_message(w["user_id"], f"✅ To'lov muvaffaqiyatli amalga oshirildi! Miqdor: {human(w['amount'])} so'm\nPul 24 soat ichida karta hisobingizga tushadi.")
        except:
            pass
        bot.answer_callback_query(call.id, "✅ So'rov tasdiqlandi va foydalanuvchiga xabar yuborildi.")
        bot.send_message(call.from_user.id, f"✅ Withdraw {wid} tasdiqlandi.")
    except Exception as e:
        # just log
        print("admin_pay_callback error:", e)
        try:
            bot.answer_callback_query(call.id, "Xatolik yuz berdi.")
        except:
            pass

# Admin step handlers
def broadcast_all(msg):
    if msg.from_user.id != ADMIN_USER_ID:
        return
    text = msg.text
    count = 0
    for uid in list(data["users"].keys()):
        try:
            bot.send_message(int(uid), text)
            count += 1
            time.sleep(0.03)
        except:
            pass
    bot.send_message(msg.from_user.id, f"📣 Xabar {count} foydalanuvchiga yuborildi.")

def ask_admin_message_userid(msg):
    if msg.from_user.id != ADMIN_USER_ID:
        return
    try:
        uid = int(msg.text.strip())
    except:
        bot.send_message(msg.from_user.id, "ID noto'g'ri. Bekor qilindi.")
        return
    bot.send_message(msg.from_user.id, "Endi yuboriladigan xabarni yozing:")
    bot.register_next_step_handler(msg, lambda m: send_to_user(uid, m.text, msg.from_user.id))

def send_to_user(uid, text, admin_chat):
    try:
        bot.send_message(uid, text)
        bot.send_message(admin_chat, "✅ Xabar yuborildi.")
    except Exception as e:
        bot.send_message(admin_chat, f"❌ Xatolik: {e}")

def admin_confirm_withdraw(msg):
    if msg.from_user.id != ADMIN_USER_ID:
        return
    wid = msg.text.strip()
    if wid not in data["withdraws"]:
        bot.send_message(msg.from_user.id, "Withdraw ID topilmadi.")
        return
    w = data["withdraws"][wid]
    if w["status"] == "paid":
        bot.send_message(msg.from_user.id, "Bu so'rov oldin tasdiqlangan.")
        return
    w["status"] = "paid"
    # deduct balance
    uid = str(w["user_id"])
    if uid in data["users"]:
        data["users"][uid]["balance"] = max(0, data["users"][uid].get("balance",0) - w["amount"])
    save_data(data)
    # notify user
    try:
        bot.send_message(w["user_id"], f"✅ To'lov muvaffaqiyatli amalga oshirildi! Miqdor: {human(w['amount'])} so'm\nPul 24 soat ichida karta hisobingizga tushadi.")
    except:
        pass
    bot.send_message(msg.from_user.id, "✅ To'lov tasdiqlandi.")

# ---------- simple commands ----------
@bot.message_handler(commands=['stats'])
def cmd_stats(m):
    if m.from_user.id != ADMIN_USER_ID:
        bot.reply_to(m, "Faqat adminga.")
        return
    tot = len(data.get("users", {}))
    bot.reply_to(m, f"Foydalanuvchilar soni: {tot}")

# ---------- run ----------
if __name__ == "__main__":
    print("Bot ishga tushmoqda...")
    # safe continuous loop: agar xatolik bo'lsa qayta urinish
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except KeyboardInterrupt:
            print("Stopped by user")
            break
        except Exception as e:
            print("Bot xato:", e)
            # kutib turib qayta ishga tushirish
            time.sleep(5)