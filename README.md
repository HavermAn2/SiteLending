About project: Its a personal website for Inst(slavrada_official) Which technologies were used: FastAPI, TelegramAPI,TelegramWebhook. Main feature: booking the dates and admin panel in Telegram. If you wanna test this site u must:

Run frontend on the basic localhost:5500
Run virtual environment (.venv)
Install all requirements (pip install -r requirements.txt)
Run Backend (uvicorn main:app --reload)
If u wanna test all features u must connect webhook:
Create a new TG bot, get a bot token;
In my case was used (ngrock) - install it from any app shop, run it with command ( ngrock http 8000), copy the ngrock public link;
In browser write (https://api.telegram.org/botBotToken/setWebhook?url=NGROCK_LINK/telegram/webhook
Create Tg group, get Group_id, add 2 topics and get their ID
Write BOT_TOKEN, GROUP_ID, ORDERS_TOPIC_ID, UPDATES_TOPIC_ID in .env file
I have the plan to add a few commands: remove/cancel bookings, auto-create Telegram booking posts after a date is selected on the website. And finally deploy and host the project for production
