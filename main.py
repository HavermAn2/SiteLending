import os, re
from fastapi import FastAPI, HTTPException,Request
from datetime import date
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
import httpx
import json
from pathlib import Path
import datetime 
import sqlite3


load_dotenv("pass.env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    if not BOT_TOKEN or not CHAT_ID:
        raise HTTPException(500, "Bot token/chat id не заданы")

    text = (
        f"*Новая заявка с лендинга*\n"
        f"👤 *Имя:* {esc_md_v2(data.name)}\n"
        f"✉️ *Email:* {esc_md_v2(str(data.phone))}\n"
        f"📝 *Сообщение:* {esc_md_v2(data.message or '')}\n"
        f"📅 *Дата:* {esc_md_v2(data.day.isoformat())}\n"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "MarkdownV2"}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        jr = r.json()
        if r.status_code != 200 or not jr.get("ok"):
            raise HTTPException(502, f"Telegram error: {jr}")
    return {"ok": True}





DATA_FILE = Path("data/content.json")


@app.post("/webhook")
async def telegram_webhook(req: Request):
    body = await req.json()
    if "message" in body and "text" in body["message"]:
        text = body["message"]["text"]
        load_request(text)#Obrabotka input s bota

    return {"ok": True,"message": body}
@app.get("/bookings")
def get_bookings():
    con = sqlite3.connect("data/booking.db")
    cur = con.cursor()
    cur.execute("SELECT date FROM bookings")
    rows = cur.fetchall()
    con.close()
    dates = [row[0] for row in rows]  

    return {"dates": dates}

    
def load_request(text:str):
    txt = text.strip()
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"Articles": []}, ensure_ascii=False, indent=2))
    if txt.startswith("/add"):
        save_message(text)
    if txt.startswith("/remove"):
        remove_message(text)
    if txt.startswith("/book"):
        book_date(text)


def save_message(text: str):
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"Articles": []}, ensure_ascii=False, indent=2))
    data = json.loads(DATA_FILE.read_text(encoding="utf-8")) # загрузить данные из файла
    articles = data.get("Articles")
    text_without_pref=text.removeprefix("/add")
    parts = text_without_pref.split("@", 1)  # разрезать только по первому "!"
    name = parts[0].strip()
    description = parts[1].strip() if len(parts) > 1 else ""
    _id = len(articles)+1
    txt = [("id", _id), ("name", name), ("description", description)]
    artticle_data= dict(txt)
    articles.append(artticle_data)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), # сохранить обратно
        encoding="utf-8"
    )
def remove_message(text: str) -> bool:
    txt = str(text).strip()
    digits = "".join(ch for ch in txt if ch.isdigit())
    if not digits:
        return False
    art_id = int(digits)  

    if not DATA_FILE.exists():
        return False  # файла нет – нечего удалять

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    articles = data.get("Articles", [])

    # отфильтровать статьи, оставив все, кроме нужного id
    new_articles = [a for a in articles if a.get("id") != art_id]
    for i, val in enumerate(new_articles, start=1):  # начинаем с 1
        val["id"] = i   # или str(i), если id должны быть строками

    

    # если длина не изменилась – такой id не нашли
    if len(new_articles) == len(articles):
        return False

    # сохранить обратно в файл
    data["Articles"] = new_articles
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return True

def book_date(text:str):
    con = sqlite3.connect("data/booking.db")
    cur = con.cursor()
    date=text.removeprefix("/book").strip()
    new_date=str(date)
    cur.execute("INSERT INTO bookings (date) VALUES (?)",(new_date,))
    con.commit()
    con.close()
    return True


def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"cards": []}
    raw = DATA_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return {"cards": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data.get("cards"), list):
        data["cards"] = []
    return data


def save_data(data: dict) -> None:
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_card_from_text(text: str) -> None:
    data = load_data()
    cards = data["cards"]
    new_id = (cards[-1]["id"] + 1) if cards else 1
    # можно разбить текст на заголовок и тело, например:
    # "Заголовок | Текст карточки"
    if " | " in text:
        title, body = text.split(" | ", 1)
    else:
        title = text[:40]      # первые 40 символов в заголовок
        body = text
    cards.append({
        "id": new_id,
        "title": title.strip(),
        "text": body.strip(),
        "created_at": datetime.utcnow().isoformat()
    })



 

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)   
# https://api.telegram.org/bot8433125749:AAF8gzZ7lfw0xaBpi69k9ve8vafEbP_oevM/getWebhookInfo


