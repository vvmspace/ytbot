# 🎩 The Distinguished YouTube Retrieval Bot (Async Edition)

*An exquisite asynchronous utility for the procurement of high-fidelity audiovisual recordings, leveraging a refined queue system for unmatched reliability.*

---

## 📜 An Introduction

Pray, allow me to introduce the new and improved architecture of this remarkable tool. To ensure that no request is lost to the whims of server timeouts, the bot now operates as a duo: a **Webhook** and a **Worker**.

The Webhook acts as a poised receptionist, accepting your requests and archiving them within a MongoDB vault. The Worker, a diligent archivist running upon your local machine, retrieves these requests and procures the media with surgical precision.

## ✨ Distinguished Features

- **Asynchronous Queueing**: Requests are safely stored in MongoDB, ensuring that even the most substantial recordings are processed without interruption.
- **Local Procurement**: By running the worker locally, the bot avoids the uncouth bot-detection systems of the cloud, utilizing your own residential connection for a more seamless experience.
- **Tiered Delivery**: The bot notifies the user at every stage—from the initial archiving to the final delivery of both visual and auditory components.
- **Fastidious Naming**: Filenames are formatted with the utmost care: `video_name-channel_name` (spaces to `_`, pipes to `-`), ensuring a tidy archive.

## 🛠 The Process of Implementation

### I. The Prerequisites
One must possess:
- A **Telegram API Key** (obtained via [@BotFather](https://t.me/botfather)).
- A **MongoDB Connection String** (a cluster on MongoDB Atlas is most recommended).

### II. The Webhook (Vercel Deployment)
1. **The Repository**: Deposit this codebase into a GitHub or GitLab repository.
2. **The Connection**: Link said repository to your Vercel account.
3. **The Secrets**: In the Vercel dashboard, introduce the following environment variables:
   - `TELEGRAM_API_KEY`: *Your bot token.*
   - `MONGODB_CONNECTION_STRING`: *Your MongoDB URI.*
4. **The Activation**: Inform Telegram of the webhook's residence:
   `npx sethook <YOUR_TELEGRAM_API_KEY> https://<YOUR_SITE_NAME>.vercel.app/api/webhook`

### III. The Worker (Local Execution)
The worker must be run on a local machine where `yt-dlp` can operate freely.

1. **Environment**: Create a `.env` file in the root directory:
   ```env
   TELEGRAM_API_KEY=your_token_here
   MONGODB_CONNECTION_STRING=your_mongodb_uri_here
   ```
2. **Dependencies**: Install the required libraries:
   `pip install -r requirements.txt`
3. **Execution**: Awaken the worker:
   `python worker.py`

## ⚖️ A Note on Technicalities

The Worker utilizes `yt-dlp` to download the finest available `mp4` and `m4a` formats. By operating locally, it bypasses the "bot detection" issues common to serverless environments. The files are sent to the user as `Documents` to preserve their high-fidelity quality and correct filenames.

---

*Developed with poise and precision. May your queue be short and your quality superlative.*
