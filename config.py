import os

BOT_TOKEN = os.environ["BOT_TOKEN"]
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_USERNAME = os.environ["BOT_USERNAME"]
MONGODB_URI = os.environ["MONGODB_URI"]
OWNER_ID = int(os.environ.get("OWNER_ID", 123456789))  # Add your Telegram ID
PORT = int(os.environ.get("PORT", 8080))
