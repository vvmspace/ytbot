const { Telegraf } = require("telegraf");
const ytdl = require("@distube/ytdl-core");
require("dotenv").config();

const bot = new Telegraf(process.env.TELEGRAM_API_KEY);

function formatFilename(title, channel) {
  const fullTitle = `${title}-${channel}`;
  // Replace spaces with _, | with -, and remove non-printable characters
  return fullTitle
    .replace(/\s+/g, "_")
    .replace(/\|/g, "-")
    .replace(/[^\x20-\x7E]/g, "") // Remove non-printable characters
    .trim();
}

bot.on("text", async (ctx) => {
  const messageText = ctx.message.text;

  if (!ytdl.validateURL(messageText)) {
    return; // Ignore non-YouTube links
  }

  try {
    await ctx.reply(
      "Pray, wait a moment while I procure your recording with the utmost diligence... 🎩⏳",
    );

    const info = await ytdl.getInfo(messageText);
    const title = info.videoDetails.title;
    const channel = info.videoDetails.author.name;
    const safeName = formatFilename(title, channel);

    // Get best audio and video formats
    const formats = ytdl.filterFormats(info.formats, "audioandvideo");
    const audioFormats = ytdl.filterFormats(info.formats, "audio");

    // Best video (mp4)
    const bestVideo =
      formats.find((f) => f.mimeType.includes("video/mp4")) || formats[0];
    // Best audio (m4a)
    const bestAudio =
      audioFormats.find((f) => f.mimeType.includes("audio/mp4")) ||
      audioFormats[0];

    if (!bestVideo || !bestAudio) {
      throw new Error("Could not find suitable formats");
    }

    // We send both. Telegram will download them in parallel and deliver them.
    // We use the URL directly to avoid Netlify timeout/disk limits.

    const videoPromise = bot.telegram
      .sendVideo(ctx.chat.id, bestVideo.url, {
        caption: `${safeName}.mp4`,
        filename: `${safeName}.mp4`,
      })
      .catch((err) => console.error("Video send error:", err));

    const audioPromise = bot.telegram
      .sendAudio(ctx.chat.id, bestAudio.url, {
        caption: `${safeName}.m4a`,
        filename: `${safeName}.m4a`,
      })
      .catch((err) => console.error("Audio send error:", err));

    await Promise.all([videoPromise, audioPromise]);
  } catch (error) {
    console.error("Error processing YouTube link:", error);
    let errorMessage =
      "I regret to inform you that a most unfortunate error has occurred whilst processing your request.";

    const msg = error.message.toLowerCase();
    let emoji = "⚠️";
    if (msg.includes("unavailable")) {
      errorMessage =
        "It appears the recording you seek is unavailable or has been withdrawn from public view.";
      emoji = "🚫";
    } else if (msg.includes("age restricted")) {
      errorMessage =
        "I am afraid this particular content is restricted by age, and I cannot procure it for you.";
      emoji = "🔞";
    } else if (msg.includes("private")) {
      errorMessage =
        "The recording you have requested is private and therefore beyond my reach.";
      emoji = "🔒";
    } else if (msg.includes("format")) {
      errorMessage =
        "I struggled to find a suitable format for this recording that would satisfy my quality standards.";
      emoji = "🛠️";
    } else {
      errorMessage += ` Specifically, the system reports a most peculiar complication: ${error.message}`;
      emoji = "🧐";
    }
    await ctx.reply(`${errorMessage} ${emoji}`);
  }
});

exports.handler = async (event, context) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    // Telegraf's bot.handleUpdate expects the update object from Telegram
    const update = JSON.parse(event.body);
    await bot.handleUpdate(update);
    return { statusCode: 200, body: "OK" };
  } catch (error) {
    console.error("Webhook error:", error);
    return { statusCode: 500, body: "Internal Server Error" };
  }
};
