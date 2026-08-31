import telebot
import os
from flask import Flask
import threading

# Lấy thông tin an toàn từ môi trường Render
TOKEN = '8915837453:AAH0IwRjIxxJJ0IATlmuQi4-H4HBTDRx8k'
ADMIN_ID = 8218051610

bot = telebot.TeleBot(TOKEN)
user_states = {}   # Lưu trạng thái chờ link của user
pending_links = {} # Lưu liên kết giữa tin nhắn của Admin và User

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "/bypassvuotnhanh để Bypass link vuotnhanh.com.")

@bot.message_handler(commands=['bypassvuotnhanh'])
def bypass_cmd(message):
    user_states[message.chat.id] = True
    bot.reply_to(message, "Gửi Link Vuotnhanh.com Để Bypass!")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # 1. Xử lý khi ADMIN trả lời (reply) tin nhắn để gửi link đã bypass
    if chat_id == ADMIN_ID and message.reply_to_message:
        original_msg_id = message.reply_to_message.message_id
        if original_msg_id in pending_links:
            target_user_id = pending_links[original_msg_id]
            bot.send_message(target_user_id, text) # Gửi kết quả cho user
            bot.reply_to(message, "✅ Đã gửi lại cho user!")
            del pending_links[original_msg_id]
        return

    # 2. Xử lý người dùng gửi tin nhắn nhưng chưa dùng lệnh
    if not user_states.get(chat_id, False):
        bot.reply_to(message, "Dùng lệnh /bypassvuotnhanh để bypass!")
        return

    # 3. Xử lý người dùng đã dùng lệnh và gửi link
    if "vuotnhanh.com/" in text:
        user_states[chat_id] = False  # Reset trạng thái
        bot.reply_to(message, "Xong")
        
        # Chuyển tiếp link cho Admin
        msg_to_admin = bot.send_message(
            ADMIN_ID, 
            f"🔗 Link cần bypass từ [{chat_id}]:\n{text}"
        )
        # Lưu ID tin nhắn để Admin có thể reply
        pending_links[msg_to_admin.message_id] = chat_id
    else:
        bot.reply_to(message, "Vui Lòng Gửi Link Vuotnhanh.com!")

# Chạy bot
if __name__ == "__main__":
    print("Bot đang chạy...")
    bot.infinity_polling()
import telebot
import os
from flask import Flask
import threading

TOKEN = os.getenv('8915837453:AAHG_PpY_PCLf7rSwyx2_JdSxv8Qs1qFLtQ')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8218051610'))

bot = telebot.TeleBot(TOKEN)
user_states = {}
pending_links = {}

# --- Web Server nhỏ để mở cổng HTTP (giúp chọn gói Free của Render) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- Logic Telegram Bot ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, "/bypassvuotnhanh để Bypass link vuotnhanh.com.")

@bot.message_handler(commands=['bypassvuotnhanh'])
def bypass_cmd(message):
    user_states[message.chat.id] = True
    bot.reply_to(message, "Gửi Link Vuotnhanh.com Để Bypass!")

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if chat_id == ADMIN_ID and message.reply_to_message:
        original_msg_id = message.reply_to_message.message_id
        if original_msg_id in pending_links:
            target_user_id = pending_links[original_msg_id]
            bot.send_message(target_user_id, text)
            bot.reply_to(message, "✅ Đã gửi lại cho user!")
            del pending_links[original_msg_id]
        return

    if not user_states.get(chat_id, False):
        bot.reply_to(message, "Dùng lệnh /bypassvuotnhanh để bypass!")
        return

    if "vuotnhanh.com/" in text:
        user_states[chat_id] = False
        bot.reply_to(message, "Xong")
        msg_to_admin = bot.send_message(
            ADMIN_ID, 
            f"🔗 Link cần bypass từ [{chat_id}]:\n{text}"
        )
        pending_links[msg_to_admin.message_id] = chat_id
    else:
        bot.reply_to(message, "Vui Lòng Gửi Link Vuotnhanh.com!")

if __name__ == "__main__":
    # Chạy Web Server bằng luồng phụ
    threading.Thread(target=run_web).start()
    # Chạy bot Telegram
    bot.infinity_polling()
