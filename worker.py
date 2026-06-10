import os
import re
import time

import requests
import yt_dlp
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
MONGODB_CONNECTION_STRING = os.environ.get("MONGODB_CONNECTION_STRING")


def format_filename(title, channel):
    full_title = f"{title}-{channel}"
    # Replace spaces with _, | with -, and remove non-printable characters
    formatted = re.sub(r"\s+", "_", full_title)
    formatted = formatted.replace("|", "-")
    formatted = re.sub(r"[^\x20-\x7E]", "", formatted)
    return formatted.strip()


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)


def send_telegram_document(chat_id, file_path, caption):
    # Using sendDocument to ensure the file is sent as a file with the correct name
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        payload = {"chat_id": chat_id, "caption": caption}
        requests.post(url, data=payload, files=files)


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
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            title = info.get("title", "Unknown Title")
            channel = info.get("uploader", "Unknown Channel")
            safe_name = format_filename(title, channel)

            # yt-dlp might have downloaded a single file or separate video/audio
            # We need to find the actual files on disk
            import glob

            files = glob.glob(f"downloads/*{safe_name}*")  # Simplified search

            # Better: use the info to find the downloaded file paths
            # Since we use a simple outtmpl, let's find the mp4 and m4a
            # For simplicity in this worker, we'll search for the specific extensions
            # downloaded in the current directory/downloads

            # Actually, let's refine the download to be more explicit
            # and capture the filenames directly.

            # Re-extracting just for the filenames if needed,
            # but ydl.extract_info with download=True usually handles it.

            # Let's search for the files created
            import os

            all_files = os.listdir("downloads")

            video_file = None
            audio_file = None

            for f in all_files:
                if f.endswith(".mp4"):
                    video_file = os.path.join("downloads", f)
                elif f.endswith(".m4a"):
                    audio_file = os.path.join("downloads", f)

            if video_file:
                send_telegram_message(
                    chat_id, "The visual component is now ready for your perusal... 🎬"
                )
                send_telegram_document(chat_id, video_file, f"{safe_name}.mp4")

            if audio_file:
                send_telegram_message(
                    chat_id, "And now, the auditory accompaniment... 🎧"
                )
                send_telegram_document(chat_id, audio_file, f"{safe_name}.m4a")

        # Mark task as completed
        collection.update_one({"_id": task_id}, {"$set": {"status": "completed"}})

        # Clean up downloads
        import shutil

        shutil.rmtree("downloads", ignore_errors=True)

    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        send_telegram_message(
            chat_id,
            f"I regret to inform you that a complication occurred whilst retrieving your recording. ⚠️\n{str(e)}",
        )
        collection.update_one({"_id": task_id}, {"$set": {"status": "failed"}})


def main():
    print("The Distinguished Worker has awakened. Polling the archives... 🎩")

    # Ensure downloads directory exists
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    client = MongoClient(MONGODB_CONNECTION_STRING)
    db = client["ytbot_db"]
    collection = db.ytbot

    while True:
        try:
            # Find the first pending task
            task = collection.find_one({"status": "pending"})

            if task:
                print(f"Processing request for user {task['user_id']}...")
                # Mark as processing to avoid double-handling
                collection.update_one(
                    {"_id": task["_id"]}, {"$set": {"status": "processing"}}
                )
                process_task(task, collection)
                print("Task completed successfully.")
            else:
                # No tasks, sleep for a bit
                time.sleep(10)
        except Exception as e:
            print(f"Worker encountered an error: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()
