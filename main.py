import os, re
from fastapi import FastAPI, HTTPException,Request
from datetime import date
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
import httpx
import sqlite3
import aiosqlite
import anyio
#===============Tokens=======================
load_dotenv(".env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
ORDERS_TOPIC_ID=os.getenv("ORDERS_TOPIC_ID")
UPDATES_TOPIC_ID=int(os.getenv("UPDATES_TOPIC_ID"))
#============================================
app = FastAPI()

# Разрешаем фронту стучаться (сузь домены на проде)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def esc_md_v2(s: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s or "")# Экранируем спецсимволы для MarkdownV2, чтобы не падало с ошибкой


class SimpleBooking(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone:str
    day: date|None=None
    message: str | None = Field(None, max_length=300)

@app.post("/data")
async def send_to_telegram(data: SimpleBooking):
    if not BOT_TOKEN or not ORDERS_TOPIC_ID:
        raise HTTPException(500, "Bot token/chat id не заданы")

    text = (
        f"*Новая заявка с лендинга*\n"
        f"👤 *Имя:* {esc_md_v2(data.name)}\n"
        f"✉️ *Number:* {esc_md_v2(str(data.phone))}\n"
        f"📝 *Message:* {esc_md_v2(data.message or '')}\n"
        f"📅 *Date:* {esc_md_v2(data.day.isoformat())}\n"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": GROUP_ID,
        "message_thread_id": ORDERS_TOPIC_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        jr = r.json()
        if r.status_code != 200 or not jr.get("ok"):
            raise HTTPException(502, f"Telegram error: {jr}")
    return {"ok": True}




@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.json()
    message = body.get("message", {})
    thread_id = message.get("message_thread_id")  # id темы
    if thread_id != UPDATES_TOPIC_ID:
        return
    
    text = message.get("text") or message.get("caption")
    photo = message.get("photo") 
    if text:
        txt = text.strip()
        if txt.startswith("/add"):
            await save_message(text, photo)
        if txt.startswith("/remove"):
            await remove_message(text)
        if txt.startswith("/book"):
            book_date(text)

    return {"ok": True, "message": body}


def message_parcing(text:str):
    
    if text.startswith("/add"):
        text_without_pref = text.removeprefix("/add").strip()
        parts = text_without_pref.split("@", 1)
        name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        return [name,description]
    if text.startswith("/remove"):
        text_without_pref = text.removeprefix("/remove").strip()
        return name
    if text.startswith("/book"):
        text_without_pref = text.removeprefix("/book").strip()
        parts = text_without_pref.split("@", 1)
        name = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        return [name,description]


async def save_message(text: str, photo):
    title, desc = message_parcing(text)

    photo_path = None
    if photo:
        try:
            photo_id = photo[-1]["file_id"]  # самое большое фото
            photo_path = await get_photo_path(photo_id)
        except (TypeError, IndexError, KeyError):
            photo_path = None

    async with aiosqlite.connect("data/art-updates.db") as con:
        await con.execute(
            "INSERT INTO photos (title, description, photo_url) VALUES (?, ?, ?)",
            (title, desc, photo_path)
        )
        await con.commit()

async def get_photo_path(photo_id: str) -> str | None:
    if not BOT_TOKEN:
        raise HTTPException(500, "Bot token/chat id не заданы")

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={"file_id": photo_id}
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            print(f"Telegram getFile error: {data}")
            return None

        file_path = data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    local_path = await download_image(file_url, folder="src")
    return local_path
        



async def download_image(url: str, folder: str="src") -> str | None:
    os.makedirs(folder, exist_ok=True)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()

        # content_type = response.headers.get("Content-Type", "")
        # if not content_type.startswith("image/"):
        #     print("selam")
        #     return None

        filename = url.split("/")[-1] or "image.jpg"
        path = os.path.join(folder, filename)

        with open(path, "wb") as f:
            f.write(response.content)

        return path


@app.get("/get_card_info")
def get_c():
    con = sqlite3.connect("data/art-updates.db")
    cur = con.cursor()
    cur.execute("SELECT id, title, description, photo_url FROM photos")
    rows = cur.fetchall()
    con.close()

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








@app.get("/bookings")
def get_bookings():
    con = sqlite3.connect("data/booking.db")
    cur = con.cursor()
    cur.execute("SELECT date FROM bookings")
    con.commit()
    rows = cur.fetchall()
    con.close()
    dates = [row[0] for row in rows]  

    return {"dates": dates}

    
DB_PATH = "data/art-updates.db"


async def remove_message(tit: str) -> bool:
    text_without_pref = tit.removeprefix("/remove").strip()
    print(text_without_pref)

    try:
        async with aiosqlite.connect(DB_PATH) as con:
            cur = await con.cursor()

            # 1. znajdź rekord
            await cur.execute(
                "SELECT * FROM photos WHERE title = ?",
                (text_without_pref,)
            )
            rows = await cur.fetchall()

            if not rows:
                print("Nic nie znaleziono w bazie")
                return False

            # 2. usuń plik(i) z dysku
            local_jpg_paths = [row[3] for row in rows]  # zakładamy ścieżkę w kolumnie nr 4
            for path in local_jpg_paths:
                try:
                    # usunięcie pliku w wątku, żeby nie blokować event loopa
                    await anyio.to_thread.run_sync(os.remove, path)
                except OSError as e:
                    print(f"Nie udało się usunąć pliku {path}: {e}")

            # 3. usuń rekordy z bazy
            await cur.execute(
                "DELETE FROM photos WHERE title = ?",
                (text_without_pref,)
            )
            await con.commit()

            return True

    except aiosqlite.Error as e:
        print(f"Error in DB: {e}")
        return False
    

def book_date(text:str):
    con = sqlite3.connect("data/booking.db")
    cur = con.cursor()
    date=text.removeprefix("/book").strip()
    new_date=str(date)
    cur.execute("INSERT INTO bookings (date) VALUES (?)",(new_date,))
    con.commit()
    con.close()
    return True





 

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)   



