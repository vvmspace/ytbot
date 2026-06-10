import json
import os
import re
import shutil
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
                        "Pray, wait a moment while I begin my investigations... 🎩⏳",
                    )
                    send_telegram_message(
                        chat_id,
                        "Searching the archives for the most superior formats... 🔍",
                    )

                    ydl_opts = {
                        "format": "best",
                        "quiet": True,
                        "no_warnings": True,
                    }

                    # Handle cookies to bypass bot detection
                    local_cookies_path = os.path.join(
                        os.path.dirname(__file__), "cookies.txt"
                    )
                    tmp_cookies_path = "/tmp/cookies.txt"
                    cookies_used = False

                    if os.path.exists(local_cookies_path):
                        # Copy local cookies to /tmp to avoid Read-only file system error on Vercel
                        shutil.copy(local_cookies_path, tmp_cookies_path)
                        ydl_opts["cookiefile"] = tmp_cookies_path
                        cookies_used = True
                    else:
                        yt_cookies = os.environ.get("YT_COOKIES")
                        if yt_cookies:
                            with open(tmp_cookies_path, "w") as f:
                                f.write(yt_cookies)
                            ydl_opts["cookiefile"] = tmp_cookies_path
                            cookies_used = True

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(text, download=False)
                        title = info.get("title", "Unknown Title")
                        channel = info.get("uploader", "Unknown Channel")
                        safe_name = format_filename(title, channel)

                        # Extract direct URLs
                        formats = info.get("formats", [])
                        best_video_url = None
                        best_audio_url = None

                        # TIER 1: Attempt to find the ideal mp4/m4a combination
                        video_mp4 = [
                            f
                            for f in formats
                            if f.get("vcodec") != "none" and f.get("ext") == "mp4"
                        ]
                        audio_m4a = [
                            f
                            for f in formats
                            if f.get("acodec") != "none" and f.get("ext") == "m4a"
                        ]

                        if video_mp4 and audio_m4a:
                            video_mp4.sort(
                                key=lambda x: x.get("height", 0), reverse=True
                            )
                            audio_m4a.sort(key=lambda x: x.get("abr", 0), reverse=True)
                            best_video_url = video_mp4[0].get("url")
                            best_audio_url = audio_m4a[0].get("url")
                        else:
                            # TIER 2: Fallback to the absolute best available regardless of extension
                            all_videos = [
                                f for f in formats if f.get("vcodec") != "none"
                            ]
                            all_audios = [
                                f for f in formats if f.get("acodec") != "none"
                            ]

                            if all_videos:
                                all_videos.sort(
                                    key=lambda x: x.get("height", 0), reverse=True
                                )
                                best_video_url = all_videos[0].get("url")

                            if all_audios:
                                all_audios.sort(
                                    key=lambda x: x.get("abr", 0), reverse=True
                                )
                                best_audio_url = all_audios[0].get("url")

                        # If we found absolutely nothing, we admit defeat and list formats
                        if not best_video_url and not best_audio_url:
                            fmt_details = []
                            for f in formats:
                                ext = f.get("ext", "unknown")
                                res = f.get(
                                    "resolution", f.get("format_note", "unknown")
                                )
                                type_mark = ""
                                if (
                                    f.get("vcodec") != "none"
                                    and f.get("acodec") != "none"
                                ):
                                    type_mark = "va"
                                elif f.get("vcodec") != "none":
                                    type_mark = "v"
                                elif f.get("acodec") != "none":
                                    type_mark = "a"
                                fmt_details.append(f"{ext} ({res}) [{type_mark}]")

                            formats_summary = ", ".join(fmt_details[:12])
                            if len(fmt_details) > 12:
                                formats_summary += " ..."

                            raise Exception(
                                f"I struggled to find any suitable format for this recording. I have observed the following alternatives: {formats_summary}"
                            )

                        # Send whatever we managed to procure
                        if best_video_url:
                            send_telegram_message(
                                chat_id,
                                "I have discovered the finest quality. Now, I shall dispatch the video... 🎬",
                            )
                            send_telegram_video(chat_id, best_video_url, safe_name)
                        if best_audio_url:
                            send_telegram_message(
                                chat_id,
                                "And now, the auditory accompaniment... 🎧",
                            )
                            send_telegram_audio(chat_id, best_audio_url, safe_name)

                except Exception as e:
                    error_msg = str(e).lower()
                    emoji = "🧐"
                    posh_error = "I regret to inform you that a most unfortunate error has occurred whilst processing your request."

                    if "sign in to confirm you’re not a bot" in error_msg:
                        if cookies_used:
                            posh_error = "Alas, YouTube has mistaken my diligence for that of a common automaton, despite the credentials provided. It appears your cookies have expired or are no longer accepted. Pray, provide a fresh set of cookies in the cookies.txt file."
                        else:
                            posh_error = "Alas, YouTube has mistaken my diligence for that of a common automaton. To resolve this, pray provide your session cookies in the YT_COOKIES environment variable or a cookies.txt file in the api directory."
                        emoji = "🍪"
                    elif "unavailable" in error_msg:
                        posh_error = "It appears the recording you seek is unavailable or has been withdrawn from public view."
                        emoji = "🚫"
                    elif "age restricted" in error_msg:
                        posh_error = "I am afraid this particular content is restricted by age, and I cannot procure it for you."
                        emoji = "🔞"
                    elif "private" in error_msg:
                        posh_error = "The recording you have requested is reported as Private or restricted. If you know this to be incorrect, it may be that the provided cookies are no longer valid. Alas, the recording remains an impenetrable mystery."
                        emoji = "🔒"
                        posh_error += f" (Technical detail: {str(e)})"
                    elif "format" in error_msg:
                        if "I have observed the following alternatives" in error_msg:
                            posh_error = str(e)
                        else:
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
