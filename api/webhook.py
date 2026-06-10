import json
import os
import re
from http.server import BaseHTTPRequestHandler

import requests
import yt_dlp

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")


def format_filename(title, channel):
    full_title = f"{title}-{channel}"
    # Replace spaces with _, | with -, and remove non-printable characters
    # [^\x20-\x7E] matches any character outside the standard printable ASCII range
    formatted = re.sub(r"\s+", "_", full_title)
    formatted = formatted.replace("|", "-")
    formatted = re.sub(r"[^\x20-\x7E]", "", formatted)
    return formatted.strip()


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)


def send_telegram_video(chat_id, video_url, filename):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendVideo"
    payload = {
        "chat_id": chat_id,
        "video": video_url,
        "caption": f"{filename}.mp4",
        "filename": f"{filename}.mp4",
    }
    requests.post(url, json=payload)


def send_telegram_audio(chat_id, audio_url, filename):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendAudio"
    payload = {
        "chat_id": chat_id,
        "audio": audio_url,
        "caption": f"{filename}.m4a",
        "filename": f"{filename}.m4a",
    }
    requests.post(url, json=payload)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data.decode("utf-8"))

        if "message" in update and "text" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"]

            # Basic YouTube URL validation
            if "youtube.com" in text or "youtu.be" in text:
                try:
                    send_telegram_message(
                        chat_id,
                        "Pray, wait a moment while I procure your recording with the utmost diligence... 🎩⏳",
                    )

                    ydl_opts = {
                        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                        "quiet": True,
                        "no_warnings": True,
                    }

                    # Handle cookies to bypass bot detection
                    yt_cookies = os.environ.get("YT_COOKIES")
                    if yt_cookies:
                        cookies_path = "/tmp/cookies.txt"
                        with open(cookies_path, "w") as f:
                            f.write(yt_cookies)
                        ydl_opts["cookiefile"] = cookies_path

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(text, download=False)
                        title = info.get("title", "Unknown Title")
                        channel = info.get("uploader", "Unknown Channel")
                        safe_name = format_filename(title, channel)

                        # Extract direct URLs
                        # Note: yt-dlp usually provides a combined url if format is best,
                        # but for separate mp4/m4a we need to look at the formats list.
                        formats = info.get("formats", [])

                        best_video_url = None
                        best_audio_url = None

                        # Find best mp4 video
                        for f in formats:
                            if f.get("vcodec") != "none" and f.get("ext") == "mp4":
                                best_video_url = f.get("url")
                                break

                        # Find best m4a audio
                        for f in formats:
                            if f.get("acodec") != "none" and f.get("ext") == "m4a":
                                best_audio_url = f.get("url")
                                break

                        if not best_video_url or not best_audio_url:
                            raise Exception(
                                "I struggled to find a suitable format for this recording that would satisfy my quality standards."
                            )

                        # Send to Telegram
                        send_telegram_video(chat_id, best_video_url, safe_name)
                        send_telegram_audio(chat_id, best_audio_url, safe_name)

                except Exception as e:
                    error_msg = str(e).lower()
                    emoji = "🧐"
                    posh_error = "I regret to inform you that a most unfortunate error has occurred whilst processing your request."

                    if "sign in to confirm you’re not a bot" in error_msg:
                        posh_error = "Alas, YouTube has mistaken my diligence for that of a common automaton. To resolve this, pray provide your session cookies in the YT_COOKIES environment variable."
                        emoji = "🍪"
                    elif "unavailable" in error_msg:
                        posh_error = "It appears the recording you seek is unavailable or has been withdrawn from public view."
                        emoji = "🚫"
                    elif "age restricted" in error_msg:
                        posh_error = "I am afraid this particular content is restricted by age, and I cannot procure it for you."
                        emoji = "🔞"
                    elif "private" in error_msg:
                        posh_error = "The recording you have requested is private and therefore beyond my reach."
                        emoji = "🔒"
                    elif "format" in error_msg:
                        posh_error = "I struggled to find a suitable format for this recording that would satisfy my quality standards."
                        emoji = "🛠️"
                    else:
                        posh_error += f" Specifically, the system reports a most peculiar complication: {str(e)}"
                        emoji = "⚠️"

                    send_telegram_message(chat_id, f"{posh_error} {emoji}")

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"The bot is dormant, awaiting its instructions.")
