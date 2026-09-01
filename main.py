import os
import re
import asyncio
import threading
import sqlite3
import datetime
import telebot
from flask import Flask
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# **Cấu hình hệ thống**
TOKEN = os.getenv('TOKEN', 'YOUR_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))
BOT_USERNAME = "BypassVuotNhanhCom_bot"
bot = telebot.TeleBot(TOKEN)

# **Khởi tạo Database SQLite**
db_lock = threading.Lock()
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()
with db_lock:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            free_limit INTEGER DEFAULT 2,
            last_date TEXT,
            referred_by INTEGER,
            first_bypass INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

def get_user(user_id, referred_by=None):
    today = datetime.date.today().strftime('%Y-%m-%d')
    with db_lock:
        cursor.execute("SELECT balance, free_limit, last_date, first_bypass FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute("INSERT INTO users (user_id, balance, free_limit, last_date, referred_by) VALUES (?, 0, 2, ?, ?)", (user_id, today, referred_by))
            conn.commit()
            return {"balance": 0, "free_limit": 2, "first_bypass": 0}
        balance, free_limit, last_date, first_bypass = user
        if last_date != today:
            free_limit = 2
            cursor.execute("UPDATE users SET free_limit = 2, last_date = ? WHERE user_id = ?", (today, user_id))
            conn.commit()
        return {"balance": balance, "free_limit": free_limit, "first_bypass": first_bypass}

def update_balance(user_id, amount, free_change=0):
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance + ?, free_limit = free_limit + ? WHERE user_id = ?", (amount, free_change, user_id))
        conn.commit()

# **Thuật toán Playwright Tự động Vượt Link**
async def run_automation(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)

        try:
            # 1. Mở trang rút gọn
            await page.goto(url, wait_until="networkidle", timeout=30000)
            body_text = await page.inner_text("body")
            
            # Trích xuất từ khóa và domain mục tiêu tự động từ trang
            kw_match = re.search(r"Từ khóa:?\s*([^\n]+)", body_text, re.IGNORECASE)
            dom_match = re.search(r"(?:Website|Trang web):?\s*([a-zA-Z0-9.-]+)", body_text, re.IGNORECASE)
            keyword = kw_match.group(1).strip() if kw_match else "thông cống nghẹt"
            target_domain = dom_match.group(1).strip() if dom_match else "thongcong"

            # 2. Tìm kiếm trên Google
            google_page = await context.new_page()
            await google_page.goto("https://www.google.com", wait_until="networkidle")
            search_box = await google_page.wait_for_selector("textarea[name='q'], input[name='q']")
            await search_box.fill(keyword)
            await google_page.keyboard.press("Enter")
            await google_page.wait_for_load_state("networkidle")

            # 3. Click vào domain mục tiêu
            links = await google_page.query_selector_all("a")
            target_link = None
            for link in links:
                href = await link.get_attribute("href")
                if href and target_domain in href:
                    target_link = link
                    break
            if not target_link:
                await browser.close()
                return None, "Không tìm thấy website mục tiêu trên Google."

            await target_link.click()
            await google_page.wait_for_load_state("networkidle")

            # 4. Cuộn trang, bấm lấy mã và chờ đếm ngược
            await google_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await google_page.wait_for_timeout(2000)
            
            get_code_btn = await google_page.query_selector("text=/LẤY MÃ|GET CODE|NHẬN MÃ/i")
            if get_code_btn:
                await get_code_btn.click()
                await google_page.wait_for_timeout(65000) # Chờ đồng hồ đếm ngược
                
                code_elem = await google_page.query_selector(".code-display, #code, .get-code-val, #ma-lay")
                code = await code_elem.inner_text() if code_elem else None
                
                # 5. Nhập mã trả lại trang chính
                if code:
                    await page.bring_to_front()
                    input_box = await page.wait_for_selector("input[name='code'], input#code")
                    await input_box.fill(code.strip())
                    await page.click("button[type='submit']")
                    await page.wait_for_load_state("networkidle")
                    
                    final_url = page.url
                    await browser.close()
                    return final_url, None

            await browser.close()
            return None, "Không tìm thấy nút lấy mã hoặc hết thời gian chờ."
        except Exception as e:
            await browser.close()
            return None, f"Lỗi hệ thống: {str(e)}"

# **Flask Server duy trì 24/7 trên Render**
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# **Các lệnh Telegram Bot**
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    args = message.text.split()
    ref_by = int(args[1].split('_')[1]) if len(args) > 1 and args[1].startswith('ref_') and args[1].split('_')[1].isdigit() else None
    if ref_by == user_id: ref_by = None
    
    get_user(user_id, ref_by)
    text = (
        "👋 **Chào mừng bạn đến với Bot Vượt Link Tự Động!**\n\n"
        "Gửi link cần vượt (ontops.link, toplinks.io...) vào đây để bot tự động xử lý.\n\n"
        "🎁 **Chính sách:** Mỗi ngày 2 lượt miễn phí. Sau đó 300 xu/lượt.\n\n"
        "📌 **DANH SÁCH LỆNH:**\n"
        "🔹 /start - Mở menu hướng dẫn\n"
        "🔹 /sodu - Kiểm tra số dư và lượt miễn phí\n"
        "🔹 /myref - Lấy link giới thiệu (Nhận 1.000 xu khi bạn bè vượt link đầu)\n\n"
        "👑 **Chủ bot:** @itznvl"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['sodu'])
def sodu_cmd(message):
    user = get_user(message.from_user.id)
    text = f"💰 **TÀI KHOẢN CỦA BẠN:**\n- Số dư: **{user['balance']} xu**\n- Miễn phí hôm nay: **{user['free_limit']}/2 lượt**"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['myref'])
def myref_cmd(message):
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    text = f"🔗 **LINK GIỚI THIỆU:**\n`{ref_link}`\n\n🎁 Nhận ngay **1.000 xu** khi người được mời vượt thành công link đầu tiên."
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['thongbao'])
def thongbao_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Bạn không có quyền dùng lệnh này!")
    text = message.text.replace('/thongbao', '').strip()
    if not text:
        return bot.reply_to(message, "⚠️ Vui lòng nhập nội dung thông báo.")
    
    with db_lock:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    
    msg = bot.reply_to(message, f"⏳ Đang gửi thông báo đến {len(users)} người...")
    success, fail = 0, 0
    for u in users:
        try:
            bot.send_message(u[0], f"🔔 **THÔNG BÁO TỪ ADMIN:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except:
            fail += 1
    bot.edit_message_text(f"✅ Gửi xong! Thành công: {success}, Thất bại: {fail}", chat_id=message.chat.id, message_id=msg.message_id)

@bot.message_handler(func=lambda msg: "http" in msg.text)
def handle_link(message):
    user_id = message.from_user.id
    url = message.text.strip()
    user = get_user(user_id)
    
    if user['free_limit'] <= 0 and user['balance'] < 300:
        return bot.reply_to(message, "❌ Bạn đã hết lượt miễn phí và không đủ 300 xu. Dùng /myref để kiếm thêm xu!")

    processing_msg = bot.reply_to(message, "⏳ Đang chạy tự động hóa trình duyệt (mất khoảng 70-80s)...")
    
    # Kích hoạt Playwright xử lý ngầm
    final_url, error = asyncio.run(run_automation(url))
    
    if final_url:
        if user['free_limit'] > 0:
            update_balance(user_id, 0, -1)
        else:
            update_balance(user_id, -300, 0)
            
        if user['first_bypass'] == 0:
            with db_lock:
                cursor.execute("SELECT referred_by FROM users WHERE user_id = ? AND first_bypass = 0", (user_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    update_balance(row[0], 1000)
                    cursor.execute("UPDATE users SET first_bypass = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    try:
                        bot.send_message(row[0], "🎁 Người bạn giới thiệu đã vượt link thành công! Bạn nhận được **1.000 xu**.")
                    except: pass
                    
        bot.edit_message_text(f"✅ **Thành công!**\n🔗 Link đích:\n{final_url}", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text(f"❌ **Thất bại:** {error}", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.infinity_polling()
