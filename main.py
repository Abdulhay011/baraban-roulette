import os
import asyncio
import random
import sqlite3
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = 8603437893
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://splendid-trifle-0d621b.netlify.app")

# Database
conn = sqlite3.connect("bot.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance REAL DEFAULT 0,
    referred_by INTEGER DEFAULT NULL,
    total_wins INTEGER DEFAULT 0,
    total_games INTEGER DEFAULT 0,
    last_bonus TEXT DEFAULT NULL
)""")
c.execute("""CREATE TABLE IF NOT EXISTS roulette (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT DEFAULT 'waiting',
    total_bank REAL DEFAULT 0,
    winner_id INTEGER DEFAULT NULL,
    created_at TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    user_id INTEGER,
    amount REAL,
    chance REAL DEFAULT 0
)""")
conn.commit()

def get_user(user_id, username=""):
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, username) VALUES (?,?)", (user_id, username))
        conn.commit()
    return c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

def get_balance(user_id):
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row[0] if row else 0

def add_balance(user_id, amount):
    c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_current_game():
    c.execute("SELECT * FROM roulette WHERE status='waiting' OR status='active' ORDER BY id DESC LIMIT 1")
    return c.fetchone()

def get_game_bets(game_id):
    c.execute("SELECT * FROM bets WHERE game_id=?", (game_id,))
    return c.fetchall()

def main_menu(bal):
    keyboard = [
        [InlineKeyboardButton("🎰 Ruletka O'ynash", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("💵 Balans", callback_data="balance"),
         InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("🏆 Top", callback_data="top"),
         InlineKeyboardButton("🎁 Bonus", callback_data="bonus")],
        [InlineKeyboardButton("🔗 Referal", callback_data="referral"),
         InlineKeyboardButton("💸 Yechish", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else None
    get_user(user.id, user.username or user.first_name or "")
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user.id,))
    row = c.fetchone()
    if ref_id and ref_id != user.id and row[0] is None:
        c.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref_id, user.id))
        conn.commit()
        add_balance(ref_id, 500)
        try:
            await context.bot.send_message(ref_id, "🎉 Yangi referal! +$500 bonus!")
        except:
            pass
    bal = get_balance(user.id)
    await update.message.reply_text(
        f"🎰 *Baraban Ruletka!*\n\n"
        f"👤 {user.first_name}\n"
        f"💵 Balans: *${bal:.2f}*\n\n"
        f"Menyudan tanlang 👇",
        parse_mode="Markdown",
        reply_markup=main_menu(bal)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    get_user(user.id, user.username or user.first_name or "")

    if query.data == "balance":
        bal = get_balance(user.id)
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        await query.edit_message_text(f"💵 *Balansingiz: ${bal:.2f}*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "menu":
        bal = get_balance(user.id)
        await query.edit_message_text(
            f"🎰 *Baraban Ruletka!*\n\n💵 Balans: *${bal:.2f}*\n\nMenyudan tanlang 👇",
            parse_mode="Markdown", reply_markup=main_menu(bal)
        )

    elif query.data == "top":
        c.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
        rows = c.fetchall()
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        msg = "🏆 *Top 10:*\n\n"
        for i, row in enumerate(rows):
            msg += f"{medals[i]} @{row[0]} — ${row[1]:.2f}\n"
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "stats":
        c.execute("SELECT total_games, total_wins, balance FROM users WHERE user_id=?", (user.id,))
        row = c.fetchone()
        games, wins, bal = (row[0], row[1], row[2]) if row else (0, 0, 0)
        winrate = (wins/games*100) if games > 0 else 0
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        await query.edit_message_text(
            f"📊 *Statistika:*\n\n🎮 O'yinlar: {games}\n✅ Yutishlar: {wins}\n📈 Yutish %: {winrate:.1f}%\n💵 Balans: ${bal:.2f}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "bonus":
        c.execute("SELECT last_bonus FROM users WHERE user_id=?", (user.id,))
        row = c.fetchone()
        today = str(date.today())
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        if row and row[0] == today:
            await query.edit_message_text("❌ *Kunlik bonus olindi!*\n\nErtaga qaytib keling!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            add_balance(user.id, 50)
            c.execute("UPDATE users SET last_bonus=? WHERE user_id=?", (today, user.id))
            conn.commit()
            new_bal = get_balance(user.id)
            await query.edit_message_text(f"🎁 *+$50 kunlik bonus!*\n\n💵 Balans: ${new_bal:.2f}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "referral":
        ref_link = f"https://t.me/{context.bot.username}?start={user.id}"
        c.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user.id,))
        count = c.fetchone()[0]
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        await query.edit_message_text(
            f"🔗 *Referal:*\n\nHar yangi foydalanuvchi: +$500\nReferallar: {count} ta\n\n{ref_link}",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "withdraw":
        bal = get_balance(user.id)
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="menu")]]
        await query.edit_message_text(
            f"💸 *Pul yechish:*\n\n💵 Balans: ${bal:.2f}\n\nAdminga yozing: @Abdulhay011\nMinimal: $100",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(f"❌ Admin emas! ID: {update.effective_user.id}")
        return
    try:
        uid = int(context.args[0])
        amount = float(context.args[1])
        get_user(uid)
        add_balance(uid, amount)
        await update.message.reply_text(f"✅ {uid} ga +${amount:.2f} qo'shildi!")
        try:
            await context.bot.send_message(uid, f"💵 Balansingizga +${amount:.2f} qo'shildi!")
        except:
            pass
    except:
        await update.message.reply_text("❗ Format: /addbalance [id] [summa]")

async def removebalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        amount = float(context.args[1])
        add_balance(uid, -amount)
        await update.message.reply_text(f"✅ {uid} dan -${amount:.2f} ayirildi!")
    except:
        await update.message.reply_text("❗ Format: /removebalance [id] [summa]")

async def allusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    c.execute("SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 20")
    rows = c.fetchall()
    msg = "👥 Foydalanuvchilar:\n\n"
    for row in rows:
        msg += f"ID: {row[0]} | @{row[1]} | ${row[2]:.2f}\n"
    await update.message.reply_text(msg)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addbalance", addbalance))
app.add_handler(CommandHandler("removebalance", removebalance))
app.add_handler(CommandHandler("allusers", allusers))
app.add_handler(CallbackQueryHandler(button))

print("Bot ishga tushdi!")
app.run_polling()
