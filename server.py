from threading import Thread
from flask import Flask
from SONALI import app as pyro_app
import logging
import os

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Flask app
web = Flask(__name__)

@web.route('/')
def home():
    return "AFK Bot is Online! ⚡"

def run_pyro():
    """Run the Pyrogram client"""
    logger.info("Starting Pyrogram client...")
    
    # Check if bot is running
    if pyro_app.is_initialized:
        logger.info("Bot is already running")
    else:
        pyro_app.start()
        logger.info("Bot started successfully")
        
        # Send startup notification to bot owner
        owner_id = int(os.environ.get("OWNER_ID", 0))
        if owner_id:
            try:
                pyro_app.send_message(
                    owner_id,
                    "✅ AFK Bot Started Successfully!\n"
                    f"🤖 Username: @{os.environ['BOT_USERNAME']}"
                )
            except Exception as e:
                logger.error(f"Startup notification failed: {e}")
        
        pyro_app.idle()

if __name__ == "__main__":
    # Start Pyrogram bot
    pyro_thread = Thread(target=run_pyro, daemon=True)
    pyro_thread.start()
    
    # Start Flask server
    web.run(host='0.0.0.0', port=8080)
