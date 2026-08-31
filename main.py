import os
import threading
import telebot
from flask import Flask

# 1. Lấy Token và Admin ID an toàn từ môi trường Render (Ẩn hoàn toàn khỏi GitHub)
TOKEN = os.getenv('TOKEN')
ADMIN_ID_RAW = os.getenv('ADMIN_ID', '0')
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 0

bot = telebot.TeleBot(TOKEN)
user_states = {}
pending_links = {}

# 2. Khởi tạo Web Server Flask (Giúp chọn gói Web Service Free trên Render)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 3. Xử lý Lệnh Telegram Bot
@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "Chào bạn! Sử dụng lệnh /bypassvuotnhanh để bắt đầu.")

@bot.message_handler(commands=['bypassvuotnhanh'])
def bypass_cmd(message):
    user_states[message.chat.id] = True
    bot.reply_to(message, "Vui lòng gửi link Vuotnhanh.com để xử lý!")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""

    # Xử lý khi Admin Reply phản hồi cho User
    if chat_id == ADMIN_ID and message.reply_to_message:
        original_msg_id = message.reply_to_message.message_id
        if original_msg_id in pending_links:
            target_user_id = pending_links[original_msg_id]
            bot.send_message(target_user_id, text)
            bot.reply_to(message, "✅ Đã gửi lại kết quả cho User!")
            del pending_links[original_msg_id]
        return

    # Kiểm tra xem User đã gõ lệnh khởi động chưa
    if not user_states.get(chat_id, False):
        bot.reply_to(message, "Vui lòng gõ lệnh /bypassvuotnhanh trước khi gửi link!")
        return

    # Nhận link vuotnhanh.com và chuyển tiếp cho Admin
    if "vuotnhanh.com/" in text:
        user_states[chat_id] = False
        bot.reply_to(message, "Xong! Link của bạn đã được gửi cho Admin xử lý.")
        msg_to_admin = bot.send_message(
            ADMIN_ID, 
            f"🔗 Link cần bypass từ [{chat_id}]:\n{text}"
        )
        pending_links[msg_to_admin.message_id] = chat_id
    else:
        bot.reply_to(message, "Vui lòng gửi đúng đường link Vuotnhanh.com!")

if __name__ == "__main__":
    # Chạy Web Server dưới dạng luồng phụ (daemon)
    threading.Thread(target=run_web, daemon=True).start()
    
    # Chạy Telegram Bot
    print("Bot Telegram đang khởi chạy...")
    bot.infinity_polling()
