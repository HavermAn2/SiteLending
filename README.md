About project: Its a personal website for Inst(slavrada_official) 
Which frameworks were used: FastAPI, TelegramAPI,TelegramWebhook. 
Main feature: booking the dates and admin panel in Telegram.
If you wanna test this site u must:
  1) Run frontend on the basic localhost:5500
  2) Run virtual environment (.venv)
  3) Install all requirements (pip install -r requirements.txt)
  4) Run Backend (uvicorn main:app --reload)
  5) If u wanna test all features u must connect webhook:
      1. Create a new TG bot, get a bot token;
      2. In my case was used (ngrock) - install it from any app shop, run it with command ( ngrock http 8000), copy the ngrock public link;
      3. In browser write (https://api.telegram.org/botBotToken/setWebhook?url=NGROCK_LINK/telegram/webhook
  6) Create Tg group, get Group_id, add 2 topics and get their ID
  7) Write BOT_TOKEN, GROUP_ID, ORDERS_TOPIC_ID, UPDATES_TOPIC_ID in .env file

I have the plan to add a few commands: remove/cancel bookings, auto-create Telegram booking posts after a date is selected on the website. And finally deploy and host the project for production
