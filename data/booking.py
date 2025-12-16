import calendar
import datetime
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import time
from collections import deque
from telegram.ext import ContextTypes
import asyncio
from telegram.error import RetryAfter, TimedOut, BadRequest
import aiohttp 
load_dotenv(".env")


# ========== КАЛЕНДАРЬ (выбор дат) ==========

def build_calendar(year: int, month: int, selected_dates: list[str] | None = None) -> InlineKeyboardMarkup:
    if selected_dates is None:
        selected_dates = []

    keyboard: list[list[InlineKeyboardButton]] = []

    # заголовок с месяцем
    month_name = datetime.date(year, month, 1).strftime("%B %Y")
    keyboard.append([InlineKeyboardButton(month_name, callback_data="IGNORE")])

    # дни недели
    keyboard.append([
        InlineKeyboardButton(d, callback_data="IGNORE")
        for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    ])

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    for week in month_days:
        row: list[InlineKeyboardButton] = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
            else:
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                text = f"✅{day}" if date_str in selected_dates else str(day)
                row.append(
                    InlineKeyboardButton(
                        text,
                        callback_data=f"DATE:{date_str}",
                    )
                )
        keyboard.append(row)

    # кнопка завершения выбора дат
    keyboard.append([InlineKeyboardButton("Done", callback_data="DONE_DATES")])

    return InlineKeyboardMarkup(keyboard)


# ========== КЛАВА ВРЕМЕНИ ДЛЯ КОНКРЕТНОЙ ДАТЫ ==========

def build_time_keyboard(date_str: str, selected_times: list[str] | None = None) -> InlineKeyboardMarkup:
    if selected_times is None:
        selected_times = []

    # какие времена доступны
    times = [
        "08:00", "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00", "15:00",
        "16:00", "17:00", "18:00", "19:00",
        "20:00", "21:00", "22:00", "23:00",
    ]

    keyboard: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for t in times:
        # если уже выбрано – помечаем галкой
        text = f"✅{t}" if t in selected_times else t
        row.append(
            InlineKeyboardButton(
                text,
                callback_data=f"TIME:{date_str}:{t}",
            )
        )
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # кнопка "Готово с этой датой" — перейти к следующей дате
    keyboard.append([InlineKeyboardButton("Set this date", callback_data="NEXT_DATE")])
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="CANCEL_ALL")])

    return InlineKeyboardMarkup(keyboard)







async def ask_time_for_current_date(query, context: ContextTypes.DEFAULT_TYPE):
    pending_dates: list[str] = context.user_data.get("pending_dates", [])
    date_times: dict[str, list[str]] = context.user_data.get("date_times", {})
    current_index: int = context.user_data.get("current_index", 0)

    if current_index >= len(pending_dates):
        # все даты обработаны — показываем итог
        if not date_times:
            await safe_edit_message_text(query, "Nothing was chose.")
            return

        lines = []
        for d in sorted(date_times.keys()):
            times = sorted(date_times[d])
            times_str = ", ".join(times) if times else "—"
            lines.append(f"{d} — {times_str}")
        text = "Вы выбрали:\n" + "\n".join(lines)

        # отправляем данные на бекенд
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:8000/your_available_dates",
                    json={"dates_times": date_times},
                ) as res:
                    if res.status == 200:
                        text += "\n\nYour available days are set."
                    else:
                        text += f"\n\nServer returned status {res.status}."
        except Exception as e:
            text += f"\n\nError while sending data: {e}"

        await safe_edit_message_text(query, text)
        return

    current_date = pending_dates[current_index]
    selected_times = date_times.get(current_date, [])
    markup = build_time_keyboard(current_date, selected_times)

    await safe_edit_message_text(
        query,
        f"Choose one or a few for: {current_date}, PRESS «Set this date»:",
        reply_markup=markup,
    )




# ========== HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # очищаем состояние
    context.user_data["selected_dates"] = []
    context.user_data["pending_dates"] = []
    context.user_data["date_times"] = {}
    context.user_data["current_index"] = 0
    today = datetime.date.today()
    markup = build_calendar(today.year, today.month, context.user_data["selected_dates"])
    await update.message.reply_text(
        "Choose one or a few and PRESS «Done»:",
        reply_markup=markup,
    )


async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    await safe_answer_callback_query(query)

    selected_dates: list[str] = context.user_data.get("selected_dates", [])
    pending_dates: list[str] = context.user_data.get("pending_dates", [])
    date_times: dict[str, list[str]] = context.user_data.get("date_times", {})
    current_index: int = context.user_data.get("current_index", 0)

    # --- выбор дат ---
    if data.startswith("DATE:"):
        date_str = data.split(":", 1)[1]

        if date_str in selected_dates:
            selected_dates.remove(date_str)
        else:
            selected_dates.append(date_str)

        context.user_data["selected_dates"] = selected_dates

        year, month, _ = map(int, date_str.split("-"))
        markup = build_calendar(year, month, selected_dates)
        await safe_edit_message_reply_markup(query, reply_markup=markup)

    elif data == "DONE_DATES":
        if not selected_dates:
            await safe_edit_message_text(query, "Nothing was chose.")
            return

        # фиксируем порядок дат
        pending_dates = sorted(selected_dates)
        context.user_data["pending_dates"] = pending_dates
        context.user_data["date_times"] = {}
        context.user_data["current_index"] = 0

        await ask_time_for_current_date(query, context)

    # --- выбор времени (мультивыбор для конкретной даты) ---
    elif data.startswith("TIME:"):
        _, date_str, time_str = data.split(":", 2)

        times_for_date = date_times.get(date_str, [])
        if time_str in times_for_date:
            times_for_date.remove(time_str)
        else:
            times_for_date.append(time_str)
        date_times[date_str] = times_for_date
        context.user_data["date_times"] = date_times

        # перерисовываем клаву времени для той же даты
        markup = build_time_keyboard(date_str, times_for_date)
        await safe_edit_message_reply_markup(query, reply_markup=markup)

    # --- переходим к следующей дате ---
    elif data == "NEXT_DATE":
        current_index += 1
        context.user_data["current_index"] = current_index
        await ask_time_for_current_date(query, context)

    elif data == "CANCEL_ALL":
        context.user_data.clear()
        await safe_edit_message_text(query, "The process was canceled.")





# Очередь задач на редактирование: (bot, chat_id, message_id, "text"/"markup", payload, reply_markup)
_edit_queue: deque[tuple] = deque()
_edit_worker_running = False

MIN_EDIT_INTERVAL = 1  

async def safe_answer_callback_query(query):
    try:
        await query.answer()
    except RetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            await query.answer()
        except Exception:
            pass
    except BadRequest as e:
        msg = str(e).lower()
        # "Query is too old and response timeout expired or query id is invalid"
        if "query is too old" in msg or "query id is invalid" in msg:
            return
        raise
    except TimedOut:
        return


async def safe_edit_message_reply_markup(query, reply_markup=None):
    if not query.message:
        return

    bot = query.get_bot()
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    # kind="markup", payload можно оставить None
    _edit_queue.append((bot, chat_id, message_id, "markup", None, reply_markup))

    asyncio.create_task(_edit_worker())



async def safe_edit_message_text(query, text: str, reply_markup=None):
    if not query.message:
        return

    bot = query.get_bot()
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    _edit_queue.append((bot, chat_id, message_id, "text", text, reply_markup))# Кладём задачу в очередь: kind="text", payload=text
    asyncio.create_task(_edit_worker())# Стартуем воркер, если он ещё не запущен



async def _edit_worker():
    global _edit_worker_running

    if _edit_worker_running:
        return  # уже запущен

    _edit_worker_running = True

    try:
        while _edit_queue:
            bot, chat_id, message_id, kind, payload, reply_markup = _edit_queue.popleft()

            try:
                if kind == "text":
                    # payload = text
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=payload,
                        reply_markup=reply_markup,
                    )
                elif kind == "markup":
                    # payload игнорим, важно только reply_markup
                    await bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reply_markup,
                    )
            except RetryAfter as e:
                # если телега попросила подождать — ждём и пробуем ещё раз
                print(f"[TG RetryAfter in _edit_worker]: waiting {e.retry_after} sec")
                await asyncio.sleep(e.retry_after)
                try:
                    if kind == "text":
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=payload,
                            reply_markup=reply_markup,
                        )
                    elif kind == "markup":
                        await bot.edit_message_reply_markup(
                            chat_id=chat_id,
                            message_id=message_id,
                            reply_markup=reply_markup,
                        )
                except Exception:
                    # если и после повтора не вышло — просто пропускаем
                    pass
            except BadRequest as e:
                msg = str(e)
                # типичные "не страшные" ошибки
                if "Message is not modified" in msg:
                    pass
                elif "query is too old" in msg or "message to edit not found" in msg:
                    pass
                else:
                    # остальные BadRequest лучше увидеть в логах
                    print("[TG BadRequest in _edit_worker]:", e)
            except TimedOut:
                # телега не ответила — забили
                pass

            # пауза между запросами к Telegram, чтобы не ловить RetryAfter
            await asyncio.sleep(MIN_EDIT_INTERVAL)
    finally:
        _edit_worker_running = False
