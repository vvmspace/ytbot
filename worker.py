import glob
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import yt_dlp
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
MONGODB_CONNECTION_STRING = os.environ.get("MONGODB_CONNECTION_STRING")
MAX_FILE_SIZE = 45 * 1024 * 1024  # 45MB safety limit


def format_filename(title, channel):
    full_title = f"{title}-{channel}"
    formatted = re.sub(r"\s+", "_", full_title)
    formatted = formatted.replace("|", "-")
    formatted = re.sub(r"[^\x20-\x7E]", "", formatted)
    return formatted.strip()


def send_telegram_message(chat_id, text, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id
    requests.post(url, json=payload)


def send_telegram_video(chat_id, file_path, caption, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendVideo"
    with open(file_path, "rb") as f:
        files = {"video": f}
        payload = {"chat_id": chat_id, "caption": caption}
        if reply_to_id:
            payload["reply_to_message_id"] = reply_to_id
        response = requests.post(url, data=payload, files=files, timeout=60)
        if response.status_code != 200:
            raise Exception(
                f"Telegram API error {response.status_code}: {response.text}"
            )


def send_telegram_audio(chat_id, file_path, caption, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendAudio"
    with open(file_path, "rb") as f:
        files = {"audio": f}
        payload = {"chat_id": chat_id, "caption": caption}
        if reply_to_id:
            payload["reply_to_message_id"] = reply_to_id
        response = requests.post(url, data=payload, files=files, timeout=60)
        if response.status_code != 200:
            raise Exception(
                f"Telegram API error {response.status_code}: {response.text}"
            )
            raise Exception(
                f"Telegram API error {response.status_code}: {response.text}"
            )


def procure_and_send(url, path, media_type, chat_id, safe_name):
    """Downloads a specific URL and immediately dispatches it to the user."""
    try:
        # Procurement
        with yt_dlp.YoutubeDL(
            {"outtmpl": path, "quiet": True, "no_warnings": True}
        ) as ydl:
            ydl.download([url])

        # Immediate Delivery
        if media_type == "video":
            send_telegram_message(
                chat_id, "The visual component is now ready for your perusal... 🎬"
            )
            send_telegram_video(chat_id, path, f"{safe_name}.mp4")
        elif media_type == "audio":
            send_telegram_message(chat_id, "And now, the auditory accompaniment... 🎧")
            send_telegram_audio(chat_id, path, f"{safe_name}.m4a")

        return True
    except Exception as e:
        print(f"Procurement failed for {media_type} {url}: {e}")
        return False


def process_task(task, collection):
    chat_id = task["user_id"]
    link = task["link"]
    task_id = task["_id"]

    try:
        send_telegram_message(
            chat_id,
            "I have commenced the procurement of your recording. Pray, attend as I retrieve the finest quality... 🔍",
        )

        ydl_opts = {
            "format": "best",
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            title = info.get("title", "Unknown Title")
            channel = info.get("uploader", "Unknown Channel")
            safe_name = format_filename(title, channel)
            formats = info.get("formats", [])

            best_video_url = None
            best_audio_url = None

            def get_size(f):
                return f.get("filesize") or f.get("filesize_approx", float("inf"))

            # TIER 1: Best mp4/m4a that fit within size limit
            video_mp4 = [
                f
                for f in formats
                if f.get("vcodec") != "none"
                and f.get("ext") == "mp4"
                and get_size(f) <= MAX_FILE_SIZE
            ]
            audio_m4a = [
                f
                for f in formats
                if f.get("acodec") != "none"
                and f.get("ext") == "m4a"
                and get_size(f) <= MAX_FILE_SIZE
            ]

            if video_mp4 and audio_m4a:
                video_mp4.sort(key=lambda x: x.get("height", 0), reverse=True)
                audio_m4a.sort(key=lambda x: x.get("abr", 0), reverse=True)
                best_video_url = video_mp4[0].get("url")
                best_audio_url = audio_m4a[0].get("url")
            else:
                # TIER 2: Best of any extension that fit within size limit
                all_videos = [
                    f
                    for f in formats
                    if f.get("vcodec") != "none" and get_size(f) <= MAX_FILE_SIZE
                ]
                all_audios = [
                    f
                    for f in formats
                    if f.get("acodec") != "none" and get_size(f) <= MAX_FILE_SIZE
                ]

                if all_videos:
                    all_videos.sort(key=lambda x: x.get("height", 0), reverse=True)
                    best_video_url = all_videos[0].get("url")
                if all_audios:
                    all_audios.sort(key=lambda x: x.get("abr", 0), reverse=True)
                    best_audio_url = all_audios[0].get("url")

            if not best_video_url and not best_audio_url:
                raise Exception(
                    "The recording is simply too gargantuan for the Telegram Bot API. No version fits within the 50MB limit."
                )

            # Prepare paths
            v_path = (
                os.path.join("downloads", f"{safe_name}.mp4")
                if best_video_url
                else None
            )
            a_path = (
                os.path.join("downloads", f"{safe_name}.m4a")
                if best_audio_url
                else None
            )

            # Parallel Procurement and Immediate Delivery
            download_tasks = []
            if best_video_url:
                download_tasks.append((best_video_url, v_path, "video"))
            if best_audio_url:
                download_tasks.append((best_audio_url, a_path, "audio"))

            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        procure_and_send, url, path, mtype, chat_id, safe_name
                    )
                    for url, path, mtype in download_tasks
                ]
                # Wait for all to complete before updating status
                for future in futures:
                    future.result()

        collection.update_one({"_id": task_id}, {"$set": {"status": "completed"}})
        shutil.rmtree("downloads", ignore_errors=True)

    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        send_telegram_message(
            chat_id,
            f"I regret to inform you that a complication occurred whilst retrieving your recording. ⚠️\n{str(e)}",
        )
        collection.update_one({"_id": task_id}, {"$set": {"status": "failed"}})


def main():
    print("The Distinguished Worker has awakened for a brief appointment. 🎩")
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    client = MongoClient(MONGODB_CONNECTION_STRING)
    db = client["ytbot_db"]
    collection = db.ytbot

    try:
        task = collection.find_one({"status": "pending"})
        if task:
            print(f"Processing request for user {task['user_id']}...")
            collection.update_one(
                {"_id": task["_id"]}, {"$set": {"status": "processing"}}
            )
            process_task(task, collection)
            print("Task completed successfully.")
        else:
            print("The archives are currently empty. No pending tasks to attend to.")
    except Exception as e:
        print(f"Worker encountered a critical error: {e}")


if __name__ == "__main__":
    main()
