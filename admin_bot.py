import json
import sqlite3
import time
import requests

TOKEN = "69739360:S7A0aDnK4ivtCWJlnhmfnXQsn5hibIC5VcA"
BASE_URL = f"https://api.splus.ir/bot{TOKEN}"
ADMIN_ID = 48198481  # آیدی عددی ادمین

# دیکشنری برای مدیریت مراحل مکالمه با ادمین (برای افزایش/کاهش موجودی)
admin_steps = {}


# ---------------------------------------------------------------------------
# دیتابیس (همون shop_data.db که ربات فروش می‌سازه)
# ---------------------------------------------------------------------------

def get_shop_db_connection():
    conn = sqlite3.connect("shop_data.db")
    return conn


def get_wallet_db(user_id):
    conn = get_shop_db_connection()
    c = conn.cursor()
    c.execute("SELECT wallet FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None


def update_wallet_db(user_id, amount):
    conn = get_shop_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET wallet = wallet + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    changed = c.rowcount
    conn.close()
    return changed > 0


def get_full_stats():
    conn = get_shop_db_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT SUM(wallet) FROM users")
    total_wallet = c.fetchone()[0] or 0

    c.execute("SELECT COUNT(*), SUM(gb), SUM(price) FROM user_configs")
    row = c.fetchone()
    total_configs = row[0] or 0
    total_gb = row[1] or 0
    total_revenue = row[2] or 0

    c.execute("SELECT COUNT(*) FROM topup_requests WHERE status='pending'")
    pending_topups = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
    open_tickets = c.fetchone()[0]

    conn.close()
    return {
        "total_users": total_users,
        "total_wallet": total_wallet,
        "total_configs": total_configs,
        "total_gb": total_gb,
        "total_revenue": total_revenue,
        "pending_topups": pending_topups,
        "open_tickets": open_tickets,
    }


# ---------------------------------------------------------------------------
# API تلگرام
# ---------------------------------------------------------------------------

def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        res = requests.post(url, json=payload, timeout=15)
        return res.json()
    except Exception:
        return {"ok": False}


def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 3}
    if offset:
        params["offset"] = offset
    try:
        res = requests.get(url, params=params, timeout=10)
        return res.json()
    except Exception:
        return {"ok": False, "result": []}


# ---------------------------------------------------------------------------
# رابط کاربری ادمین
# ---------------------------------------------------------------------------

def admin_menu(chat_id, text="🔧 پنل مدیریت و آمار کاربران:"):
    keyboard = {
        "keyboard": [
            [{"text": "📊 آمار کامل کاربران"}],
            [{"text": "➕ افزایش موجودی"}, {"text": "➖ کاهش موجودی"}],
        ],
        "resize_keyboard": True,
    }
    send_message(chat_id, text, reply_markup=keyboard)


def format_stats_text(stats):
    return (
        "📊 آمار کامل ربات:\n\n"
        f"👥 تعداد کل کاربران: {stats['total_users']:,}\n"
        f"👛 مجموع موجودی کیف پول‌ها: {stats['total_wallet']:,} تومان\n\n"
        f"📦 تعداد کل کانفیگ‌های فروخته‌شده: {stats['total_configs']:,}\n"
        f"💾 مجموع حجم فروخته‌شده: {stats['total_gb']:,.1f} GB\n"
        f"💵 مجموع درآمد: {stats['total_revenue']:,} تومان\n\n"
        f"⏳ درخواست‌های شارژ در انتظار تایید: {stats['pending_topups']:,}\n"
        f"🎫 تیکت‌های باز: {stats['open_tickets']:,}"
    )


# ---------------------------------------------------------------------------
# حلقه‌ی اصلی
# ---------------------------------------------------------------------------

print("📊 ربات مدیریت و آمار روشن شد...")
last_update_id = 0

while True:
    try:
        updates = get_updates(last_update_id + 1)

        if updates.get("ok") and updates.get("result"):
            for update in updates["result"]:
                last_update_id = update["update_id"]

                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    text = message.get("text", "")

                    # فقط ادمین اجازه‌ی استفاده از این ربات رو داره
                    if chat_id != ADMIN_ID:
                        continue

                    step = admin_steps.get(str(chat_id), {})

                    if text == "/start":
                        admin_steps[str(chat_id)] = {}
                        admin_menu(chat_id)

                    elif text == "📊 آمار کامل کاربران":
                        stats = get_full_stats()
                        send_message(chat_id, format_stats_text(stats))

                    elif text == "➕ افزایش موجودی":
                        admin_steps[str(chat_id)] = {"step": "inc_ask_user_id", "sign": 1}
                        send_message(chat_id, "🆔 آیدی عددی کاربری که می‌خواهید موجودیش افزایش پیدا کند را وارد کنید:")

                    elif text == "➖ کاهش موجودی":
                        admin_steps[str(chat_id)] = {"step": "inc_ask_user_id", "sign": -1}
                        send_message(chat_id, "🆔 آیدی عددی کاربری که می‌خواهید موجودیش کاهش پیدا کند را وارد کنید:")

                    elif step.get("step") == "inc_ask_user_id":
                        try:
                            target_id = int(text)
                            wallet = get_wallet_db(target_id)
                            if wallet is None:
                                send_message(chat_id, "⚠️ کاربری با این آیدی در دیتابیس پیدا نشد! ❌")
                                admin_steps[str(chat_id)] = {}
                            else:
                                admin_steps[str(chat_id)] = {
                                    "step": "inc_ask_amount",
                                    "sign": step.get("sign", 1),
                                    "target_id": target_id,
                                }
                                send_message(
                                    chat_id,
                                    f"👛 موجودی فعلی این کاربر: {wallet:,} تومان\n\n💰 مبلغ مورد نظر را به تومان وارد کنید:",
                                )
                        except ValueError:
                            send_message(chat_id, "⚠️ فقط آیدی عددی وارد کنید! 🔢")

                    elif step.get("step") == "inc_ask_amount":
                        try:
                            amount = int(text)
                            if amount <= 0:
                                send_message(chat_id, "⚠️ عدد بزرگ‌تر از صفر وارد کنید! ❌")
                            else:
                                target_id = step["target_id"]
                                signed_amount = amount * step.get("sign", 1)
                                update_wallet_db(target_id, signed_amount)
                                new_wallet = get_wallet_db(target_id)

                                action_word = "افزایش" if signed_amount > 0 else "کاهش"
                                send_message(
                                    chat_id,
                                    f"✅ موجودی کاربر {target_id} به مقدار {amount:,} تومان {action_word} یافت.\n"
                                    f"👛 موجودی جدید: {new_wallet:,} تومان",
                                )
                                try:
                                    send_message(
                                        target_id,
                                        f"💳 موجودی کیف پول شما به مقدار {amount:,} تومان توسط ادمین {action_word} یافت.\n"
                                        f"👛 موجودی فعلی: {new_wallet:,} تومان",
                                    )
                                except Exception:
                                    pass

                                admin_steps[str(chat_id)] = {}
                                admin_menu(chat_id)
                        except ValueError:
                            send_message(chat_id, "⚠️ فقط عدد وارد کنید (به تومان)! 🔢")

        else:
            time.sleep(1)

    except Exception as loop_error:
        print("⚠️ خطای غیرمنتظره در حلقه اصلی:", loop_error)
        time.sleep(2)
