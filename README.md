<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">
</p>

<h1 align="center">🤖 Advanced AFK Bot</h1>
<p align="center">
  A smart Telegram bot to set AFK (Away From Keyboard) statuses with text, images, GIFs, or stickers.  
  It automatically notifies others when you are AFK and when you return.
</p>

<p align="center">
  <a href="https://t.me/team_secrat_bots">
    <img src="https://img.shields.io/badge/Support%20Group-Join-orange?style=for-the-badge&logo=telegram" alt="Support Group">
  </a>
</p>

<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">
</p>

---

## ✨ Features

- 📝 **Set AFK** with:
  - 💬 Text reason (`/afk reason here`)
  - 🖼️ Reply to media (photo/GIF/sticker) with `/afk` to set media AFK
  - ⚡ Quick AFK with `/afk` or `brb`
- ⏱️ AFK reason & duration shown to people who:
  - 📢 Mention you
  - 💬 Reply to your messages
- 🔄 Auto-remove AFK when you send any message
- 👥 Works in **groups** and **private chats**
- 📩 Startup notification to the bot owner
- 💾 MongoDB-based persistent AFK storage
- 🌐 **Flask health check server** (for uptime monitoring)
- 📎 Group invite button

---

## 📦 Requirements

- 🐍 Python 3.9+
- 🍃 MongoDB database
- 🤖 Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- 🔑 Telegram API ID & API Hash from [my.telegram.org](https://my.telegram.org)

---

## ⚙️ Environment Variables

| Variable       | Required | Description                                                                 |
|----------------|----------|-----------------------------------------------------------------------------|
| `BOT_TOKEN`    | ✅ Yes    | 🤖 Bot token from [@BotFather](https://t.me/BotFather)                        |
| `API_ID`       | ✅ Yes    | 📌 API ID from [my.telegram.org](https://my.telegram.org)                     |
| `API_HASH`     | ✅ Yes    | 🔑 API Hash from [my.telegram.org](https://my.telegram.org)                   |
| `BOT_USERNAME` | ✅ Yes    | 📛 Your bot username (without @)                                             |
| `MONGODB_URI`  | ✅ Yes    | 🍃 MongoDB connection URI                                                     |
| `OWNER_ID`     | ✅ Yes    | 👤 Your Telegram numeric ID (can get from [@userinfobot](https://t.me/userinfobot)) |
| `PORT`         | ❌ No     | 🌐 Flask server port (default: `8080`)                                       |

---

## 🚀 Deploy

### ☁️ Deploy to Render (One-Click)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

---

### ☁️ Deploy to Heroku (One-Click)
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

---

## 📚 Commands

| Command           | Description                               |
|-------------------|-------------------------------------------|
| `/start` or `/help` | 📖 Show help menu                         |
| `/afk`             | 📝 Set AFK with optional reason           |
| `brb`              | ⚡ Quick AFK with optional reason         |

💡 Tip: Reply to a **photo**, **GIF**, or **sticker** with `/afk` to set media AFK.

---

## 🔗 Support

If you need help or want to suggest features, join our support group:  
[![Support Group](https://img.shields.io/badge/Support%20Group-Join-orange?style=for-the-badge&logo=telegram)](https://t.me/team_secrat_bots)

---

<p align="center">
  <img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%">
</p>

## 📝 License

📄 This project is licensed under the **MIT License**.
