# 🎩 The Distinguished YouTube Retrieval Bot

*An exquisite utility for the seamless procurement of high-fidelity audiovisual recordings from the YouTube archives, delivered with grace via the Telegram medium.*

---

## 📜 An Introduction

Pray, allow me to introduce this most remarkable piece of software engineering. This bot serves as a refined intermediary, tasked with the diligent retrieval of YouTube content. Upon receiving a link, the bot shall, with surgical precision, identify the most superior quality available in both `mp4` and `m4a` formats and deliver them post-haste to the user.

It is designed specifically for deployment upon the esteemed infrastructure of **Vercel**, employing the versatile **Python** language to ensure a performance that is as reliable as a Swiss chronometer.

## ✨ Distinguished Features

- **Surgical Quality Selection**: The bot eschews mediocrity, procuring only the finest available streams for both video and audio.
- **Fastidious Naming Conventions**: Filenames are formatted with a level of tidiness that would satisfy the most exacting archivist. Spaces are replaced by underscores, pipes by hyphens, and all uncouth non-printable characters are banished entirely.
- **Effortless Serverless Architecture**: By leveraging the brilliance of Vercel Functions, the bot operates without the burden of maintaining a permanent server.
- **Asynchronous Delivery**: In a display of efficiency, the bot dispatches both audio and video simultaneously; whichever the Telegram servers manage to procure first shall be presented to the user immediately.

## 🛠 The Process of Implementation

To bring this marvel to fruition within your own digital domain, one must proceed as follows:

### I. The Prerequisites
One must first obtain a **Telegram API Key**. This is achieved by engaging in a conversation with the esteemed [@BotFather](https://t.me/botfather) on Telegram, who shall grant you a token of authorization.

### II. Deployment to Vercel
1. **The Repository**: Deposit this codebase into a GitHub or GitLab repository of your choosing.
2. **The Connection**: Link said repository to your Vercel account.
3. **The Secret**: Within the Vercel dashboard, navigate to *Project Settings* $\rightarrow$ *Environment Variables* and introduce the following secret:
   - `TELEGRAM_API_KEY`: *Your most guarded bot token.*

### III. The Final Flourish (The Webhook)
The bot is now dormant, awaiting its instructions. To awaken it, one must inform Telegram of the bot's new residence. You may achieve this via one of the following methods.

*As a point of reference, your function URL will typically resemble this:*
`https://your-project-name.vercel.app/api/webhook`

**The Modernist Approach (Via Terminal):**
Employ the following command for a swift and efficient activation:
`npx sethook <YOUR_TELEGRAM_API_KEY> <YOUR_FUNCTION_URL>`

**The Traditionalist Approach (Via Browser):**
Pray, visit the following URL in your browser, replacing the placeholders with your actual credentials:
`https://api.telegram.org/bot<YOUR_TELEGRAM_API_KEY>/setWebhook?url=<YOUR_FUNCTION_URL>`

Upon seeing the confirmation `"OK"`, the bot is officially in service.

## ⚖️ A Note on Technicalities

To avoid the uncouth limitations of serverless timeouts and memory constraints, this implementation does not download the media to the server's local disk. Instead, it provides Telegram's servers with the direct, high-quality URLs from YouTube. This ensures a swift delivery that remains unencumbered by the constraints of the hosting environment.

---

*Developed with poise and precision. May your downloads be swift and your quality superlative.*
