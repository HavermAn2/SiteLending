import os
import re
from datetime import date
from typing import Dict, List, Optional
import anyio
import httpx
import aiosqlite
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv


# =============== LOAD TOKENS =======================
load_dotenv(".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
ORDERS_TOPIC_ID = int(os.getenv("ORDERS_TOPIC_ID"))
UPDATES_TOPIC_ID = int(os.getenv("UPDATES_TOPIC_ID"))
# ===================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= HELPERS ==========================

def esc_md_v2(s: str) -> str:
    """Экранируем текст под MarkdownV2"""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!])", r"\\\1", s or "")


# ============= MODELS ===========================

class SimpleBooking(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str
    day: date
    time: str
    message: Optional[str] = Field(None, max_length=300)


# ============= SEND TO TELEGRAM (ASYNC) =============

@app.post("/data")
async def send_to_telegram(data: SimpleBooking):
    if not BOT_TOKEN or not GROUP_ID:
        raise HTTPException(500, "Bot token/chat id не заданы")

    text = (
        f"*The New Order*\n"
        f"👤 *Name:* {esc_md_v2(data.name)}\n"
        f"📞 *Number:* {esc_md_v2(data.phone)}\n"
        f"📅 *Date:* {esc_md_v2(data.day.isoformat())}\n"
        f"⏰ *Time:* {esc_md_v2(data.time)}\n"
        f"📝 *Comment:* {esc_md_v2(data.message or '')}\n"
    )

    payload = {
        "chat_id": GROUP_ID,
        "message_thread_id": ORDERS_TOPIC_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        jr = r.json()

        if not jr.get("ok"):
            raise HTTPException(502, f"Telegram error: {jr}")

    return {"ok": True}


# ============= TELEGRAM WEBHOOK ==================

@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.json()
    message = body.get("message") or body.get("edited_message") or {}
    thread_id = message.get("message_thread_id")
    # чтобы проверить, не режет ли по thread_id — временно можно закомментить
    if thread_id != UPDATES_TOPIC_ID:
        print("Другой thread_id, игнор:", thread_id)
        return {"ok": True}
    text = (message.get("text") or message.get("caption") or "").strip()
    photo = message.get("photo")
    if not text:
        return {"ok": True}

    if text.startswith("/add"):
        print("Обрабатываем /add")
        await save_message(text, photo)

    elif text.startswith("/remove"):
        print("Обрабатываем /remove")
        await remove_message(text)

    elif text.startswith("/book"):
        print("Обрабатываем /book")
        await book_date(text)
    return {"ok": True}



def message_parcing(text: str):  # или message_parsing – главное, чтобы имя совпало
    text_without_pref = text.removeprefix("/add").strip()
    parts = text_without_pref.split("@", 1)
    name = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""
    return name, description


async def save_message(text: str, photo):
    # 1. парсим текст
    try:
        title, desc = message_parcing(text)
    except Exception as e:
        print("Ошибка парсинга /add:", e, "текст:", repr(text))
        return

    # 2. пробуем скачать фото (если есть)
    photo_path = None
    if photo:
        try:
            photo_id = photo[-1]["file_id"]  # самое большое фото
            photo_path = await get_photo_file(photo_id)
        except Exception as e:
            print("Ошибка получения фото:", e)
            photo_path = None

    # 3. сохраняем запись в БД (async)
    try:
        async with aiosqlite.connect("data/art-updates.db") as db:
            # на всякий случай создаём таблицу, если её ещё нет
            await db.execute("""
                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    photo_url TEXT
                )
            """)

            await db.execute(
                "INSERT INTO photos (title, description, photo_url) VALUES (?, ?, ?)",
                (title, desc, photo_path)
            )
            await db.commit()
        print("Запись сохранена:", title, photo_path)
    except Exception as e:
        print("Ошибка записи в БД (photos):", e)


async def get_photo_file(photo_id: str) -> str | None:
    if not BOT_TOKEN:
        print("BOT_TOKEN не задан")
        return None

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": photo_id}
        )
        r.raise_for_status()
        data = r.json()

        if not data.get("ok"):
            print("Telegram getFile error:", data)
            return None

        file_path = data["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    return await download_file(url, folder="src")


async def download_file(url: str, folder: str = "src") -> str | None:
    os.makedirs(folder, exist_ok=True)

    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        r.raise_for_status()
        content = r.content

    file_name = url.split("/")[-1] or "image.jpg"
    path = os.path.join(folder, file_name)

    # запись файла выносим в отдельную функцию, чтобы красиво передать в to_thread
    def _write_file(p: str, data: bytes):
        with open(p, "wb") as f:
            f.write(data)

    await anyio.to_thread.run_sync(_write_file, path, content)
    return path
# ============= GET CARD INFO ===================
@app.get("/get_card_info")
async def get_c():
    async with aiosqlite.connect("data/art-updates.db") as db:
        cursor = await db.execute(
            "SELECT id, title, description, photo_url FROM photos"
        )
        rows = await cursor.fetchall()
        await cursor.close()

    articles = [
        {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "photo_url": row[3],
        }
        for row in rows
    ]

    return {"Articles": articles}

# ============= REMOVE MESSAGE ===================

async def remove_message(text: str):
    title = text.strip()

    async with aiosqlite.connect("data/art-updates.db") as db:
        cur = await db.execute("SELECT photo_url FROM photos WHERE title = ?", (title,))
        rows = await cur.fetchall()

        # удалить картинки
        for (path,) in rows:
            if path:
                await anyio.to_thread.run_sync(lambda: os.remove(path))

        await db.execute("DELETE FROM photos WHERE title = ?", (title,))
        await db.commit()

    return True


# ============= BOOK DATES (FROM BOT) ===================

async def book_date(text: str):
    raw_date = text.split(" ", 1)[1].strip()

    async with aiosqlite.connect("data/booking.db") as db:
        await db.execute(
            "INSERT INTO bookings (date) VALUES (?)",
            (raw_date,)
        )
        await db.commit()
    return True


# ============= SAVE AVAILABLE DATES (FROM BOT) ========

@app.post("/your_available_dates")
async def save_available_dates(req: Request):
    data = await req.json()
    dates_times: Dict[str, List[str]] = data.get("dates_times", {})

    async with aiosqlite.connect("data/booking.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS avalible_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                UNIQUE(date, time)
            )
        """)

        for d, times in dates_times.items():
            for t in times:
                await db.execute(
                    "INSERT OR IGNORE INTO avalible_dates(date, time) VALUES (?, ?)",
                    (d, t)
                )

        await db.commit()

    return {"ok": True}


# ============= GET AVAILABLE (TO FRONTEND) ============

@app.get("/bookings")
async def get_bookings():
    async with aiosqlite.connect("data/booking.db") as db:
        cur = await db.execute("SELECT date, time FROM avalible_dates")
        rows = await cur.fetchall()

    dates_times: Dict[str, List[str]] = {}
    for d, t in rows:
        dates_times.setdefault(d, []).append(t)

    return {"dates_times": dates_times}



# ============= START SERVER + BOT =========================





def start_telegram_bot():
    from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("add_dates", booking_bot.start))
    application.add_handler(CallbackQueryHandler(booking_bot.handle_callbacks))
    application.run_polling()


if __name__ == "__main__":
    import threading
    import uvicorn
    import data.booking as booking_bot
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False) #FastAPI-сервер в главном потоке
