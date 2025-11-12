import os, re
from fastapi import FastAPI, HTTPException
from datetime import date
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
import httpx

load_dotenv("pass.env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = FastAPI()

# Разрешаем фронту стучаться (сузь домены на проде)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)



def esc_md_v2(s: str) -> str:
    # Экранируем спецсимволы для MarkdownV2, чтобы не падало с ошибкой
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', s or "")


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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)