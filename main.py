import os
import re
import asyncio
import threading
import sqlite3
import datetime
import telebot
from flask import Flask
from playwright.async_api import async_playwright

# ================= CẤU HÌNH HỆ THỐNG & BẢO MẬT TOKEN =================
TOKEN = os.getenv('TOKEN', 'YOUR_BOT_TOKEN')

print(f"--- ĐANG KIỂM TRA TOKEN ---")
print(f"Giá trị TOKEN hiện tại: {TOKEN[:5]}***" if TOKEN != 'YOUR_BOT_TOKEN' else "Chưa cấu hình TOKEN")

if not TOKEN or TOKEN == 'YOUR_BOT_TOKEN':
    raise ValueError("❌ LỖI NGHIÊM TRỌNG: Biến môi trường 'TOKEN' chưa được cấu hình trên Render hoặc đang để giá trị mặc định!")

ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))
BOT_USERNAME = os.getenv('BOT_USERNAME', 'BypassVuotNhanhCom_bot')
bot = telebot.TeleBot(TOKEN)

FREE_LIMIT = 2
PRICE_PER_LINK = 300
REF_BONUS = 1000
OWNER = "@itznvl"

# ================= DATABASE SQLITE =================
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
            free_limit = FREE_LIMIT
            cursor.execute("UPDATE users SET free_limit = ?, last_date = ? WHERE user_id = ?", (FREE_LIMIT, today, user_id))
            conn.commit()
        return {"balance": balance, "free_limit": free_limit, "first_bypass": first_bypass}

def update_balance(user_id, amount, free_change=0):
    with db_lock:
        cursor.execute("UPDATE users SET balance = balance + ?, free_limit = free_limit + ? WHERE user_id = ?", (amount, free_change, user_id))
        conn.commit()

# ================= WEB SERVER (KEEP-ALIVE RENDER) =================
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running smoothly 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= PLAYWRIGHT AUTOMATION ENGINE =================
async def run_automation(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage', 
                '--disable-blink-features=AutomationControlled'
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # Script chống phát hiện bot nguyên bản (Khắc phục lỗi import playwright-stealth)
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        page = await context.new_page()

        try:
            # 1. Truy cập link rút gọn
            await page.goto(url, wait_until="networkidle", timeout=30000)
            body_text = await page.inner_text("body")
            
            # Trích xuất từ khóa và domain mục tiêu
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
                await google_page.wait_for_timeout(65000) # Chờ đếm ngược 65 giây
                
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

# ================= TELEGRAM BOT COMMANDS =================
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
        f"🎁 **Chính sách:** Mỗi ngày có {FREE_LIMIT} lượt miễn phí. Sau đó phí là {PRICE_PER_LINK} xu/lượt.\n\n"
        "📌 **DANH SÁCH LỆNH CỦA BOT:**\n"
        "🔹 /start - Khởi động lại bot và hiển thị menu hướng dẫn.\n"
        "🔹 /sodu - Kiểm tra số dư xu và số lượt vượt miễn phí còn lại.\n"
        "🔹 /myref - Lấy link giới thiệu bạn bè (Nhận ngay 1.000 xu khi bạn bè vượt link thành công lần đầu).\n"
        "🔹 /thongbao - (Admin) Gửi thông báo đến toàn bộ người dùng.\n\n"
        f"👑 **Chủ bot:** {OWNER}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['sodu'])
def sodu_cmd(message):
    user = get_user(message.from_user.id)
    text = (
        f"💰 **THÔNG TIN TÀI KHOẢN:**\n\n"
        f"🔹 **Số dư:** {user['balance']} xu\n"
        f"🔹 **Lượt miễn phí hôm nay:** {user['free_limit']}/{FREE_LIMIT} lượt\n\n"
        f"*(Lượt miễn phí được làm mới tự động vào 00:00 hằng ngày)*"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['myref'])
def myref_cmd(message):
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"
    text = (
        f"🔗 **LINK GIỚI THIỆU CỦA BẠN:**\n\n"
        f"`{ref_link}`\n\n"
        f"*(Nhấn vào link trên để copy)*\n\n"
        f"🎁 **Phần thưởng:** Nhận ngay **{REF_BONUS} xu** khi người được mời sử dụng bot và vượt thành công link đầu tiên."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['thongbao'])
def thongbao_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ **Bạn không có quyền sử dụng lệnh này!**", parse_mode="Markdown")
    
    text = message.text.replace('/thongbao', '').strip()
    if not text:
        return bot.reply_to(message, "⚠️ **Cú pháp sai!** Vui lòng nhập nội dung.\nVD: `/thongbao Bot đang bảo trì hệ thống!`", parse_mode="Markdown")
    
    with db_lock:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
    
    msg = bot.reply_to(message, f"⏳ Đang gửi thông báo đến **{len(users)}** người dùng...", parse_mode="Markdown")
    success, fail = 0, 0
    for u in users:
        try:
            bot.send_message(u[0], f"🔔 **THÔNG BÁO TỪ ADMIN:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except:
            fail += 1
            
    bot.edit_message_text(f"✅ **GỬI THÔNG BÁO HOÀN TẤT!**\n\n🎯 Thành công: **{success}** người\n❌ Thất bại: **{fail}** người (Đã chặn bot)", 
                          chat_id=message.chat.id, message_id=msg.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: "http" in msg.text)
def handle_link(message):
    user_id = message.from_user.id
    url = message.text.strip()
    user = get_user(user_id)
    
    if user['free_limit'] <= 0 and user['balance'] < PRICE_PER_LINK:
        return bot.reply_to(message, "❌ Bạn đã hết lượt miễn phí và không đủ số dư. Dùng lệnh /myref để kiếm thêm xu!")

    processing_msg = bot.reply_to(message, "⏳ Đang tự động hóa trình duyệt giải mã (mất khoảng 70-80s)...")
    
    final_url, error = asyncio.run(run_automation(url))
    
    if final_url:
        if user['free_limit'] > 0:
            update_balance(user_id, 0, -1)
        else:
            update_balance(user_id, -PRICE_PER_LINK, 0)
            
        if user['first_bypass'] == 0:
            with db_lock:
                cursor.execute("SELECT referred_by FROM users WHERE user_id = ? AND first_bypass = 0", (user_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    update_balance(row[0], REF_BONUS)
                    cursor.execute("UPDATE users SET first_bypass = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    try:
                        bot.send_message(row[0], f"🎁 **Chúc mừng!** Người bạn giới thiệu đã vượt link thành công. Bạn nhận được **{REF_BONUS} xu**!")
                    except: pass
                    
        bot.edit_message_text(f"✅ **Vượt link thành công!**\n\n🔗 **Link đích:**\n{final_url}", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        bot.edit_message_text(f"❌ **Vượt link thất bại!**\nLỗi: {error}", chat_id=message.chat.id, message_id=processing_msg.message_id, parse_mode="Markdown")

# ================= RUN SERVER & BOT =================
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Bot đang khởi động và chạy...")
    bot.infinity_polling()
