import requests
import time
import json
import sqlite3
from datetime import datetime, timedelta

TOKEN = "69734332:hZOyl3XYuO4zd6oD7Rh-svtIwKA7gLxLVFA"
BASE_URL = "https://api.splus.ir/bot" + TOKEN
CONFIG_API = "https://su.randomatic.ir/api/v1/configs"
CONFIG_KEY = "sk_live_zuBdqrdSuX6PUPbGKi8juhAfekBgAbha"
ADMIN_ID = 48198481
PRICE_PER_GB = 3000
CARD_NUMBER = "6219861957006504"
CARD_OWNER = "کمالزاده"
MIN_TOPUP = 10000

user_steps = {}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    return sqlite3.connect('shop_data.db')


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet INTEGER DEFAULT 0)')
    c.execute('''CREATE TABLE IF NOT EXISTS user_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        sub_url TEXT,
        config_id TEXT,
        gb REAL,
        label TEXT,
        days INTEGER,
        price INTEGER,
        created_at TEXT,
        expires_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        status TEXT DEFAULT "open",
        admin_reply TEXT,
        created_at TEXT
    )''')
    c.execute('CREATE TABLE IF NOT EXISTS free_trials (user_id INTEGER PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS topup_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT "pending",
        created_at TEXT
    )''')
    conn.commit()
    conn.close()


def get_wallet_db(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT wallet FROM users WHERE user_id=?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0


def add_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, wallet) VALUES (?, ?)', (user_id, 0))
    conn.commit()
    conn.close()


def update_wallet_db(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE users SET wallet = wallet + ? WHERE user_id=?', (amount, user_id))
    conn.commit()
    conn.close()


def save_user_config(user_id, sub_url, config_id, gb, label, days, price):
    conn = get_conn()
    c = conn.cursor()
    expires_at = (datetime.now() + timedelta(days=days)).isoformat()
    c.execute('''INSERT INTO user_configs
        (user_id, sub_url, config_id, gb, label, days, price, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, sub_url, config_id, gb, label, days, price, datetime.now().isoformat(), expires_at))
    conn.commit()
    conn.close()


def get_user_configs(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''SELECT id, sub_url, config_id, gb, label, days, price, created_at, expires_at
        FROM user_configs WHERE user_id=? ORDER BY created_at DESC''', (user_id,))
    res = c.fetchall()
    conn.close()
    return res


def delete_config_from_panel(config_id):
    if not config_id:
        return True
    try:
        res = requests.delete(
            CONFIG_API + '/' + str(config_id),
            headers={'Authorization': 'Bearer ' + CONFIG_KEY},
            timeout=15
        )
        return res.status_code in (200, 201, 204)
    except Exception:
        return False


def delete_config_from_db_by_index(user_id, index):
    configs = get_user_configs(user_id)
    if 0 <= index < len(configs):
        cfg = configs[index]
        delete_config_from_panel(cfg[2])
        conn = get_conn()
        c = conn.cursor()
        c.execute('DELETE FROM user_configs WHERE id=?', (cfg[0],))
        conn.commit()
        conn.close()
        return True
    return False


def get_total_purchases(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT SUM(gb), SUM(price) FROM user_configs WHERE user_id=?', (user_id,))
    res = c.fetchone()
    conn.close()
    return (res[0] if res and res[0] else 0, res[1] if res and res[1] else 0)


def check_free_trial(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM free_trials WHERE user_id=?', (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def set_free_trial(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO free_trials (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()


def create_topup_request(user_id, amount):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO topup_requests (user_id, amount, created_at) VALUES (?, ?, ?)',
               (user_id, amount, datetime.now().isoformat()))
    conn.commit()
    req_id = c.lastrowid
    conn.close()
    return req_id


def get_topup_request(req_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, user_id, amount, status FROM topup_requests WHERE id=?', (req_id,))
    res = c.fetchone()
    conn.close()
    return res


def update_topup_status(req_id, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE topup_requests SET status=? WHERE id=?', (status, req_id))
    conn.commit()
    conn.close()


def create_ticket(user_id, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)',
               (user_id, message, datetime.now().isoformat()))
    conn.commit()
    tid = c.lastrowid
    conn.close()
    return tid


def get_ticket(ticket_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id, user_id, message, status, admin_reply, created_at FROM tickets WHERE id=?', (ticket_id,))
    res = c.fetchone()
    conn.close()
    return res


def update_ticket_status(ticket_id, status, admin_reply=None):
    conn = get_conn()
    c = conn.cursor()
    if admin_reply:
        c.execute('UPDATE tickets SET status=?, admin_reply=? WHERE id=?', (status, admin_reply, ticket_id))
    else:
        c.execute('UPDATE tickets SET status=? WHERE id=?', (status, ticket_id))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Telegram / panel API helpers
# ---------------------------------------------------------------------------

def get_updates(offset=None):
    url = BASE_URL + '/getUpdates'
    params = {'timeout': 3}
    if offset:
        params['offset'] = offset
    try:
        res = requests.get(url, params=params, timeout=10)
        return res.json()
    except Exception:
        return {'ok': False, 'result': []}


def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    url = BASE_URL + '/sendMessage'
    payload = {'chat_id': chat_id, 'text': text}
    if parse_mode:
        payload['parse_mode'] = parse_mode
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        res = requests.post(url, json=payload, timeout=15)
        return res.json()
    except Exception:
        return {'ok': False}


def send_photo(chat_id, photo_id, caption=None, parse_mode=None, reply_markup=None):
    url = BASE_URL + '/sendPhoto'
    payload = {'chat_id': chat_id, 'photo': photo_id}
    if caption:
        payload['caption'] = caption
    if parse_mode:
        payload['parse_mode'] = parse_mode
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.json()
    except Exception:
        return {'ok': False}


def answer_callback(callback_query_id):
    try:
        requests.post(BASE_URL + '/answerCallbackQuery', json={'callback_query_id': callback_query_id}, timeout=5)
    except Exception:
        pass


def make_config(gb, label, days):
    try:
        res = requests.post(
            CONFIG_API,
            headers={'Authorization': 'Bearer ' + CONFIG_KEY},
            json={'gb': gb, 'label': label, 'expiryDays': days, 'proto': 'both'},
            timeout=20
        )
        if res.status_code in (200, 201):
            data = res.json()
            return {
                'success': True,
                'sub_url': data.get('subUrl'),
                'config_id': data.get('id') or data.get('uuid') or data.get('username'),
                'data': data
            }
        return {'success': False, 'error': str(res.status_code)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def main_menu(chat_id):
    wallet = get_wallet_db(chat_id)
    keyboard = {
        'keyboard': [
            [{'text': '🛒 خرید کانفیگ 🚀'}, {'text': '🧪 تست رایگان 🎁'}],
            [{'text': '💳 شارژ کیف پول 💵'}],
            [{'text': '👤 پروفایل من 🌟'}],
            [{'text': '📋 لیست کانفیگ‌ها 📁'}, {'text': '🗑 حذف کانفیگ ❌'}],
            [{'text': '📞 پشتیبانی و ارتباط 💬'}]
        ],
        'resize_keyboard': True
    }
    text = (
        '🌟✨ به ربات فروش خوش آمدید! ✨🌟\n\n'
        '💰 نرخ هر گیگابایت: ' + f'{PRICE_PER_GB:,}' + ' تومان\n'
        '👛 موجودی کیف پول: ' + f'{wallet:,}' + ' تومان\n\n'
        '👇 لطفاً یک گزینه را انتخاب کنید:'
    )
    send_message(chat_id, text, reply_markup=keyboard)


def notify_admin_new_ticket(tid, user_id, message):
    kb = {
        'inline_keyboard': [[
            {'text': '✍️ پاسخ', 'callback_data': 'reply_ticket_' + str(tid)},
            {'text': '🔒 بستن', 'callback_data': 'close_ticket_' + str(tid)}
        ]]
    }
    txt = '🎫 تیکت جدید #' + str(tid) + '\n👤 از کاربر: ' + str(user_id) + '\n\n💬 ' + str(message)
    send_message(ADMIN_ID, txt, reply_markup=kb)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

init_db()
print('🚀🤖 ربات بدون خطا روشن شد و آماده کاره...')
last_update_id = 0

while True:
    try:
        updates = get_updates(last_update_id + 1)

        if updates.get('ok') and updates.get('result'):
            for update in updates['result']:
                last_update_id = update['update_id']

                # ------------------------------------------------------------------
                # Callback queries (inline button presses)
                # ------------------------------------------------------------------
                if 'callback_query' in update:
                    query = update['callback_query']
                    chat_id = query['message']['chat']['id']
                    data = query.get('data', '')
                    answer_callback(query['id'])

                    if data == 'confirm_purchase':
                        s = user_steps.get(str(chat_id), {})
                        if s.get('step') == 'confirm_buy':
                            gb, label, days, price = s['gb'], s['label'], s['days'], s['price']
                            if get_wallet_db(chat_id) < price:
                                send_message(chat_id, '⚠️ موجودی کیف پول کافی نیست! ❌')
                            else:
                                send_message(chat_id, '⏳ در حال ساخت کانفیگ پرسرعت... لطفاً صبور باشید 🔄')
                                res = make_config(gb, label, days)
                                if res['success'] and res['sub_url']:
                                    update_wallet_db(chat_id, -price)
                                    save_user_config(chat_id, res['sub_url'], res['config_id'], gb, label, days, price)
                                    success_text = (
                                        '🎉🎊 کانفیگ شما ساخته شد! 🥳👏\n\n'
                                        '📦 حجم: ' + str(gb) + ' گیگابایت\n'
                                        '🏷 نام: ' + str(label) + '\n'
                                        '⏳ مدت: ' + str(days) + ' روز\n'
                                        '💵 قیمت: ' + f'{price:,}' + ' تومان\n\n'
                                        '🔗 لینک سابسکریپشن:\n' + str(res['sub_url']) + '\n\n'
                                        '✨ موفق باشید! 🚀🔥'
                                    )
                                    send_message(chat_id, success_text)
                                else:
                                    send_message(chat_id, '❌ خطا در ارتباط با سرور پنل!')
                            user_steps[str(chat_id)] = {}
                            main_menu(chat_id)
                        else:
                            main_menu(chat_id)

                    elif data == 'cancel_purchase' or data == 'menu':
                        user_steps[str(chat_id)] = {}
                        main_menu(chat_id)

                    elif data.startswith('reply_ticket_'):
                        tid = int(data.split('_')[2])
                        user_steps[str(chat_id)] = {'step': 'admin_reply', 'ticket_id': tid}
                        send_message(
                            chat_id,
                            '💬 لطفاً پاسخ تیکت ' + str(tid) + ' را ارسال کنید:',
                            reply_markup={'inline_keyboard': [[{'text': '❌ انصراف', 'callback_data': 'menu'}]]}
                        )

                    elif data.startswith('close_ticket_'):
                        tid = int(data.split('_')[2])
                        update_ticket_status(tid, 'closed')
                        send_message(chat_id, '🔒 تیکت ' + str(tid) + ' بسته شد. ✅')

                    elif data.startswith('topup_acc_'):
                        req_id = int(data.split('_')[2])
                        req = get_topup_request(req_id)
                        if req and req[3] == 'pending':
                            update_topup_status(req_id, 'approved')
                            update_wallet_db(req[1], req[2])
                            send_message(req[1], '✅ کیف پول شما به مبلغ ' + f'{req[2]:,}' + ' تومان با موفقیت شارژ شد! 🥳💳')
                            send_message(ADMIN_ID, '✅ رسید شارژ درخواست #' + str(req_id) + ' تایید شد و مبلغ به کیف پول کاربر اضافه گردید.')
                        else:
                            send_message(ADMIN_ID, '⚠️ این درخواست قبلاً بررسی شده یا وجود ندارد.')

                    elif data.startswith('topup_rej_'):
                        req_id = int(data.split('_')[2])
                        req = get_topup_request(req_id)
                        if req and req[3] == 'pending':
                            update_topup_status(req_id, 'rejected')
                            send_message(req[1], '❌ رسید واریز شما توسط ادمین رد شد! لطفاً با پشتیبانی در ارتباط باشید.')
                            send_message(ADMIN_ID, '❌ رسید درخواست #' + str(req_id) + ' رد شد.')
                        else:
                            send_message(ADMIN_ID, '⚠️ این درخواست قبلاً بررسی شده یا وجود ندارد.')

                # ------------------------------------------------------------------
                # Regular messages
                # ------------------------------------------------------------------
                elif 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']
                    text = message.get('text', '')
                    step = user_steps.get(str(chat_id), {})

                    if text == '/start':
                        add_user(chat_id)
                        user_steps[str(chat_id)] = {}
                        main_menu(chat_id)

                    elif text == '🛒 خرید کانفیگ 🚀':
                        wallet = get_wallet_db(chat_id)
                        if wallet < PRICE_PER_GB:
                            send_message(chat_id, '⚠️ موجودی کافی نیست! ❌\n👛 موجودی: ' + f'{wallet:,}' + ' تومان')
                        else:
                            user_steps[str(chat_id)] = {'step': 'ask_gb'}
                            send_message(
                                chat_id,
                                '📊 چند گیگابایت نیاز دارید؟ (هر گیگ ' + f'{PRICE_PER_GB:,}' + ' تومان)\n'
                                '👛 موجودی: ' + f'{wallet:,}' + ' تومان\n\n✏️ فقط عدد حجم را بفرستید:'
                            )

                    elif text == '💳 شارژ کیف پول 💵':
                        user_steps[str(chat_id)] = {'step': 'ask_topup_amount'}
                        send_message(
                            chat_id,
                            '💳💵 لطفاً مبلغ مورد نظر برای شارژ کیف پول را به تومان وارد کنید:\n'
                            '(حداقل مبلغ: ' + f'{MIN_TOPUP:,}' + ' تومان)'
                        )

                    elif text == '🧪 تست رایگان 🎁':
                        if check_free_trial(chat_id) > 0:
                            send_message(chat_id, '⚠️ شما قبلاً تست رایگان گرفته‌اید! ❌')
                        else:
                            send_message(chat_id, '🎁 در حال ساخت تست رایگان... ⏳')
                            res = make_config(0.1, 'تست رایگان', 1)
                            if res['success'] and res['sub_url']:
                                set_free_trial(chat_id)
                                save_user_config(chat_id, res['sub_url'], res['config_id'], 0.1, 'تست رایگان', 1, 0)
                                trial_text = (
                                    '🎉🎁 تست رایگان آماده شد! 🚀\n\n'
                                    '📦 حجم: 0.1 گیگابایت\n🏷 نام: تست رایگان\n⏳ مدت: 1 روز\n\n'
                                    '🔗 لینک:\n' + str(res['sub_url']) + '\n\n✨ لذت ببرید! 🔥'
                                )
                                send_message(chat_id, trial_text)
                            else:
                                send_message(chat_id, '❌ خطا در ساخت تست رایگان!')

                    elif text == '👤 پروفایل من 🌟':
                        wallet = get_wallet_db(chat_id)
                        tg, tp = get_total_purchases(chat_id)
                        profile_text = (
                            '👤🌟 پروفایل شما:\n\n'
                            '🆔 آیدی: ' + str(chat_id) + '\n'
                            '👛 موجودی: ' + f'{wallet:,}' + ' تومان\n'
                            '📊 کل خرید: ' + f'{tg:,.1f}' + ' GB\n'
                            '💵 مجموع پرداخت: ' + f'{tp:,.0f}' + ' تومان\n\n'
                            '💎 سپاس از اعتماد شما! 🙏✨'
                        )
                        send_message(chat_id, profile_text)

                    elif text == '📋 لیست کانفیگ‌ها 📁':
                        configs = get_user_configs(chat_id)
                        if configs:
                            txt = '📁📋 لیست کانفیگ‌های شما:\n\n'
                            for i, cfg in enumerate(configs, 1):
                                txt += (
                                    '🔹 ' + str(i) + ' | 🏷 ' + str(cfg[4]) + ' | 📦 ' + str(cfg[3]) +
                                    'GB | ⏳ ' + str(cfg[5]) + ' روز\n🔗 ' + str(cfg[1]) + '\n\n'
                                )
                            send_message(chat_id, txt)
                        else:
                            send_message(chat_id, '📭 هیچ کانفیگی ثبت نکرده‌اید! ❌')

                    elif text == '🗑 حذف کانفیگ ❌':
                        configs = get_user_configs(chat_id)
                        if not configs:
                            send_message(chat_id, '📭 کانفیگی برای حذف نیست! ❌')
                        else:
                            txt = '🗑⚠️ شماره ردیف کانفیگ مورد نظر برای حذف را بفرستید:\n\n'
                            for i, cfg in enumerate(configs, 1):
                                txt += '🔹 ' + str(i) + '. نام: ' + str(cfg[4]) + ' (' + str(cfg[3]) + 'GB)\n'
                            send_message(chat_id, txt)
                            user_steps[str(chat_id)] = {'step': 'waiting_delete_id'}

                    elif text == '📞 پشتیبانی و ارتباط 💬':
                        user_steps[str(chat_id)] = {'step': 'support_message'}
                        send_message(chat_id, '💬✍️ پیام خود را برای پشتیبانی بنویسید:')

                    # ---------------- step-based flows ----------------

                    elif step.get('step') == 'ask_gb':
                        try:
                            gb = int(text)
                            if gb <= 0:
                                send_message(chat_id, '⚠️ عدد بزرگ‌تر از صفر وارد کنید! ❌')
                            else:
                                price = gb * PRICE_PER_GB
                                wallet = get_wallet_db(chat_id)
                                if wallet < price:
                                    send_message(chat_id, '⚠️ موجودی کیف پول کافی نیست! اول کیف پول خود را شارژ کنید ❌')
                                    user_steps[str(chat_id)] = {}
                                else:
                                    user_steps[str(chat_id)] = {'step': 'ask_days', 'gb': gb, 'price': price}
                                    send_message(chat_id, '⏳ کانفیگ برای چند روز نیاز دارید؟ (فقط عدد روز را بفرستید)')
                        except ValueError:
                            send_message(chat_id, '⚠️ فقط عدد وارد کنید! 🔢')

                    elif step.get('step') == 'ask_days':
                        try:
                            days = int(text)
                            if days <= 0:
                                send_message(chat_id, '⚠️ عدد بزرگ‌تر از صفر وارد کنید! ❌')
                            else:
                                user_steps[str(chat_id)]['step'] = 'ask_label'
                                user_steps[str(chat_id)]['days'] = days
                                send_message(chat_id, '🏷 یک نام دلخواه برای کانفیگ بفرستید (مثلاً اسم خودتان):')
                        except ValueError:
                            send_message(chat_id, '⚠️ فقط عدد وارد کنید! 🔢')

                    elif step.get('step') == 'ask_label':
                        label = text.strip() if text.strip() else ('کاربر-' + str(chat_id))
                        gb = step['gb']
                        days = step['days']
                        price = step['price']
                        user_steps[str(chat_id)] = {
                            'step': 'confirm_buy',
                            'gb': gb,
                            'days': days,
                            'price': price,
                            'label': label
                        }
                        confirm_text = (
                            '🧾 لطفاً جزئیات خرید را تایید کنید:\n\n'
                            '📦 حجم: ' + str(gb) + ' گیگابایت\n'
                            '🏷 نام: ' + str(label) + '\n'
                            '⏳ مدت: ' + str(days) + ' روز\n'
                            '💵 قیمت: ' + f'{price:,}' + ' تومان'
                        )
                        confirm_kb = {
                            'inline_keyboard': [[
                                {'text': '✅ تایید و پرداخت', 'callback_data': 'confirm_purchase'},
                                {'text': '❌ انصراف', 'callback_data': 'cancel_purchase'}
                            ]]
                        }
                        send_message(chat_id, confirm_text, reply_markup=confirm_kb)

                    elif step.get('step') == 'waiting_delete_id':
                        try:
                            idx = int(text) - 1
                            if delete_config_from_db_by_index(chat_id, idx):
                                send_message(chat_id, '✅ کانفیگ با موفقیت حذف شد.')
                            else:
                                send_message(chat_id, '⚠️ شماره ردیف نامعتبر است! ❌')
                        except ValueError:
                            send_message(chat_id, '⚠️ فقط عدد ردیف را وارد کنید! 🔢')
                        user_steps[str(chat_id)] = {}

                    elif step.get('step') == 'ask_topup_amount':
                        try:
                            amount = int(text)
                            if amount < MIN_TOPUP:
                                send_message(chat_id, '⚠️ حداقل مبلغ شارژ ' + f'{MIN_TOPUP:,}' + ' تومان است! لطفاً مبلغ بیشتری وارد کنید:')
                            else:
                                user_steps[str(chat_id)] = {'step': 'waiting_receipt', 'amount': amount}
                                card_text = (
                                    '💳 لطفاً مبلغ ' + f'{amount:,}' + ' تومان را به شماره کارت زیر واریز کنید:\n\n'
                                    + CARD_NUMBER + '\nبه نام: ' + CARD_OWNER + '\n\n'
                                    '📥 بعد از واریز، عکس رسید رو به ربات ارسال کن سپس ربات عکس رسید رو برای ادمین می‌فرسته.'
                                )
                                send_message(chat_id, card_text)
                        except ValueError:
                            send_message(chat_id, '⚠️ فقط عدد وارد کنید (به تومان)! 🔢')

                    elif step.get('step') == 'waiting_receipt' and 'photo' in message:
                        photo_id = message['photo'][-1]['file_id']
                        amount = step.get('amount')
                        req_id = create_topup_request(chat_id, amount)

                        send_message(chat_id, '✅ عکس رسید شما دریافت شد و برای ادمین ارسال گردید. پس از تأیید، کیف پول شما شارژ خواهد شد. 🙏')
                        user_steps[str(chat_id)] = {}
                        main_menu(chat_id)

                        admin_caption = (
                            '💳🧾 درخواست شارژ کیف پول جدید!\n\n'
                            '👤 از کاربر: ' + str(chat_id) + '\n'
                            '💵 مبلغ: ' + f'{amount:,}' + ' تومان\n'
                            '🎫 شناسه درخواست: ' + str(req_id)
                        )
                        admin_kb = {
                            'inline_keyboard': [[
                                {'text': '✅ تایید', 'callback_data': 'topup_acc_' + str(req_id)},
                                {'text': '❌ رد کردن', 'callback_data': 'topup_rej_' + str(req_id)}
                            ]]
                        }
                        send_photo(ADMIN_ID, photo_id, caption=admin_caption, reply_markup=admin_kb)

                    elif step.get('step') == 'waiting_receipt' and 'photo' not in message:
                        send_message(chat_id, '⚠️ لطفاً حتماً عکس رسید واریزی را ارسال کنید!')

                    elif step.get('step') == 'support_message':
                        tid = create_ticket(chat_id, text)
                        send_message(chat_id, '✅ پیام شما با شناسه تیکت #' + str(tid) + ' برای پشتیبانی ارسال شد. به‌زودی پاسخ داده می‌شود. 🙏')
                        notify_admin_new_ticket(tid, chat_id, text)
                        user_steps[str(chat_id)] = {}

                    elif step.get('step') == 'admin_reply' and chat_id == ADMIN_ID:
                        tid = step.get('ticket_id')
                        ticket = get_ticket(tid)
                        if ticket:
                            update_ticket_status(tid, 'answered', text)
                            send_message(ticket[1], '📩 پاسخ پشتیبانی برای تیکت #' + str(tid) + ':\n\n' + text)
                            send_message(chat_id, '✅ پاسخ برای کاربر ارسال شد.')
                        else:
                            send_message(chat_id, '⚠️ تیکت یافت نشد.')
                        user_steps[str(chat_id)] = {}

        else:
            time.sleep(1)

    except Exception as loop_error:
        print('⚠️ خطای غیرمنتظره در حلقه اصلی:', loop_error)
        time.sleep(2)
