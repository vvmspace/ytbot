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
    # Replace spaces with _
    formatted = re.sub(r"\s+", "_", full_title)
    # Replace | with -
    formatted = formatted.replace("|", "-")
    # Remove characters that are NOT word characters, dots, or hyphens
    # \w matches Unicode alphanumeric characters and underscores
    formatted = re.sub(r"[^\w\.\-]", "", formatted)
    return formatted.strip(". ")


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
        payload = {
            "chat_id": chat_id,
            "caption": caption,
            "supports_streaming": True,
        }
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


def procure_and_send(
    original_url, path, media_type, chat_id, safe_name, format_id, reply_to_id=None
):
    """Downloads a specific URL and immediately dispatches it to the user."""
    try:
        # Procurement - use original_url and format_id to bypass YouTube throttling
        # We use postprocessor_args to re-encode to a standard H.264/AAC profile.
        # This fixes proportion issues (stretching/squashing) and ensures
        # perfect compatibility with the Telegram player.
        with yt_dlp.YoutubeDL(
            {
                "outtmpl": path,
                "quiet": True,
                "no_warnings": True,
                "format": format_id,
                "merge_output_format": "mp4",
                "postprocessor_args": {
                    "ffmpeg": [
                        "-c:v",
                        "libx264",
                        "-crf",
                        "23",
                        "-preset",
                        "veryfast",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "128k",
                        "-vf",
                        "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
                    ],
                },
            }
        ) as ydl:
            ydl.download([original_url])

        # Immediate Delivery
        if media_type == "video":
            send_telegram_message(
                chat_id,
                "The visual component is now ready for your perusal... 🎬",
                reply_to_id=reply_to_id,
            )
            send_telegram_video(
                chat_id, path, f"{safe_name}.mp4", reply_to_id=reply_to_id
            )
        elif media_type == "audio":
            send_telegram_message(
                chat_id,
                "And now, the auditory accompaniment... 🎧",
                reply_to_id=reply_to_id,
            )
            send_telegram_audio(
                chat_id, path, f"{safe_name}.m4a", reply_to_id=reply_to_id
            )

        return True
    except Exception as e:
        print(f"Procurement failed for {media_type} {url}: {e}")
        return False


def process_task(task, collection):
    chat_id = task["user_id"]
    link = task["link"]
    task_id = task["_id"]
    message_id = task.get("message_id")

    # Create a unique directory for this specific task to avoid conflicts during parallel downloads
    task_dir = os.path.join("downloads", str(task_id))
    os.makedirs(task_dir, exist_ok=True)

    try:
        send_telegram_message(
            chat_id,
            "I have commenced the procurement of your recording. Pray, attend as I retrieve the finest quality... 🔍",
            reply_to_id=message_id,
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

            best_video_format = None
            best_audio_format = None

            def get_size(f):
                return f.get("filesize") or f.get("filesize_approx", float("inf"))

            # TIER 1: Find the best audio-only m4a for the separate audio file
            audio_m4a = [
                f
                for f in formats
                if f.get("acodec")
                and "mp4a" in f.get("acodec")
                and f.get("ext") == "m4a"
                and get_size(f) <= MAX_FILE_SIZE
            ]

            # TIER 2: Find the best video with sound that fits within MAX_FILE_SIZE
            # We prioritize combined formats (single file with sound) to ensure perfect proportions
            video_candidates = []

            # Option A: Combined mp4 formats (already have sound and correct proportions)
            combined_mp4 = [
                f
                for f in formats
                if f.get("vcodec") != "none"
                and f.get("acodec") != "none"
                and f.get("ext") == "mp4"
                and get_size(f) <= MAX_FILE_SIZE
            ]
            for f in combined_mp4:
                video_candidates.append(
                    {
                        "format_id": f.get("format_id"),
                        "height": f.get("height", 0),
                        "size": get_size(f),
                        "combined": True,
                    }
                )

            # Option B: Separate video (mp4) + audio (m4a) to be merged
            # Only considered as fallback if combined formats are too low quality or unavailable
            video_only_mp4 = [
                f
                for f in formats
                if f.get("vcodec")
                and "avc1" in f.get("vcodec")
                and f.get("acodec") == "none"
                and f.get("ext") == "mp4"
            ]

            # For each video stream, find the best audio stream that keeps the total under the limit
            for v in video_only_mp4:
                v_size = get_size(v)
                if v_size >= MAX_FILE_SIZE:
                    continue

                # Find best audio that fits in the remaining space
                remaining_space = MAX_FILE_SIZE - v_size
                best_a_for_v = None
                best_a_abr = 0

                for a in audio_m4a:
                    a_size = get_size(a)
                    if a_size <= remaining_space and a.get("abr", 0) > best_a_abr:
                        best_a_for_v = a
                        best_a_abr = a.get("abr", 0)

                if best_a_for_v:
                    video_candidates.append(
                        {
                            "format_id": f"{v.get('format_id')}+{best_a_for_v.get('format_id')}",
                            "height": v.get("height", 0),
                            "size": v_size + get_size(best_a_for_v),
                            "combined": False,
                        }
                    )

            # Pick the candidate with the highest resolution.
            # If heights are equal, prefer combined formats for better proportion stability.
            best_video_format = None
            if video_candidates:
                video_candidates.sort(
                    key=lambda x: (x["height"], x["combined"]), reverse=True
                )
                best_video_format = video_candidates[0]["format_id"]

            best_audio_format = None
            if audio_m4a:
                audio_m4a.sort(key=lambda x: x.get("abr", 0), reverse=True)
                best_audio_format = audio_m4a[0].get("format_id")

            if not best_video_format and not best_audio_format:
                raise Exception(
                    "The recording is simply too gargantuan for the Telegram Bot API. No version fits within the 50MB limit."
                )

            # Prepare paths
            v_path = (
                os.path.join(task_dir, f"{safe_name}.mp4")
                if best_video_format
                else None
            )
            a_path = (
                os.path.join(task_dir, f"{safe_name}.m4a")
                if best_audio_format
                else None
            )

            # Parallel Procurement and Immediate Delivery
            download_tasks = []
            if best_video_format:
                download_tasks.append((link, v_path, "video", best_video_format))
            if best_audio_format:
                download_tasks.append((link, a_path, "audio", best_audio_format))

            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        procure_and_send,
                        url,
                        path,
                        mtype,
                        chat_id,
                        safe_name,
                        fid,
                        message_id,
                    )
                    for url, path, mtype, fid in download_tasks
                ]
                for future in futures:
                    future.result()

        collection.update_one({"_id": task_id}, {"$set": {"status": "completed"}})
        shutil.rmtree(task_dir, ignore_errors=True)

    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        send_telegram_message(
            chat_id,
            f"I regret to inform you that a complication occurred whilst retrieving your recording. ⚠️\n{str(e)}",
            reply_to_id=message_id,
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
