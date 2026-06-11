import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from pymongo import MongoClient

from core.downloader import YoutubeDownloader
from core.processor import MediaProcessor
from core.telegram import TelegramClient

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("worker")

load_dotenv()

# Configuration
TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
MONGODB_CONNECTION_STRING = os.environ.get("MONGODB_CONNECTION_STRING")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
MAX_FILE_SIZE = 40 * 1024 * 1024
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", "ffprobe")

# Initialize components
tg_client = TelegramClient(TELEGRAM_API_KEY, debug=DEBUG)
downloader = YoutubeDownloader(ffmpeg_path=FFMPEG_PATH)
processor = MediaProcessor(
    max_file_size=MAX_FILE_SIZE,
    ffmpeg_path=FFMPEG_PATH,
    ffprobe_path=FFPROBE_PATH,
)


def format_filename(title, channel):
    import re

    full_title = f"{title}-{channel}"
    formatted = re.sub(r"\s+", "_", full_title)
    formatted = formatted.replace("|", "-")
    formatted = re.sub(r"[^\w\.\-]", "", formatted)
    return formatted.strip(". ")


def procure_and_send(
    url,
    path,
    media_type,
    chat_id,
    safe_name,
    format_id,
    width=None,
    height=None,
    reply_to_id=None,
):
    try:
        logger.info(f"Procuring {media_type}: {url}")
        actual_file = downloader.download(
            url, path, format_id, is_video=(media_type == "video")
        )

        final_path, duration = processor.process(actual_file, media_type, safe_name)

        if media_type == "video":
            tg_client.send_message(
                chat_id,
                "The visual component is now ready for your perusal... 🎬",
                reply_to_id=reply_to_id,
                is_informative=True,
            )
            tg_client.send_video(
                chat_id,
                final_path,
                f"{safe_name}.mp4",
                width=width,
                height=height,
                reply_to_id=reply_to_id,
                duration=int(duration),
            )
        else:
            tg_client.send_message(
                chat_id,
                "And now, the auditory accompaniment... 🎧",
                reply_to_id=reply_to_id,
                is_informative=True,
            )
            ext = "mp3" if final_path.endswith(".mp3") else "m4a"
            tg_client.send_audio(
                chat_id,
                final_path,
                f"{safe_name}.{ext}",
                reply_to_id=reply_to_id,
                duration=int(duration),
            )

        return True
    except Exception as e:
        logger.error(f"Failed to procure and send {media_type}: {e}")
        return False


def process_task(task, collection):
    chat_id, link, task_id, message_id = (
        task["user_id"],
        task["link"],
        task["_id"],
        task.get("message_id"),
    )
    confirmation_message_id = task.get("confirmation_message_id")
    task_dir = os.path.join("downloads", str(task_id))
    os.makedirs(task_dir, exist_ok=True)

    try:
        tg_client.send_message(
            chat_id,
            "I have commenced the procurement of your recording. Pray, attend as I retrieve the finest quality... 🔍",
            reply_to_id=message_id,
            is_informative=True,
        )

        info = downloader.extract_info(link)
        safe_name = format_filename(
            info.get("title", "Unknown"), info.get("uploader", "Unknown")
        )
        duration = info.get("duration", 0)

        best_a_fmt, best_v_fmt, best_v = downloader.select_formats(info, MAX_FILE_SIZE)

        if duration > 40 * 60:
            logger.info(
                f"Skipping video procurement: duration {duration}s exceeds 40m limit"
            )
            best_v_fmt = None

        audio_delivered, video_delivered = False, False
        with ThreadPoolExecutor() as executor:
            if best_a_fmt:
                if executor.submit(
                    procure_and_send,
                    link,
                    os.path.join(task_dir, f"{safe_name}.m4a"),
                    "audio",
                    chat_id,
                    safe_name,
                    best_a_fmt,
                    reply_to_id=message_id,
                ).result():
                    audio_delivered = True
            if best_v_fmt:
                if executor.submit(
                    procure_and_send,
                    link,
                    os.path.join(task_dir, f"{safe_name}.mp4"),
                    "video",
                    chat_id,
                    safe_name,
                    best_v_fmt,
                    best_v["width"],
                    best_v["height"],
                    reply_to_id=message_id,
                ).result():
                    video_delivered = True

        if not audio_delivered and not video_delivered:
            tg_client.send_message(
                chat_id,
                "I am terribly sorry, but I could not retrieve any part of your request. ⚠️",
                reply_to_id=message_id,
                is_informative=False,
            )
            status = "failed"
        else:
            status = "completed"
            if not audio_delivered:
                tg_client.send_message(
                    chat_id,
                    "The video is ready, but the audio proved most troublesome. ⚠️",
                    reply_to_id=message_id,
                    is_informative=False,
                )
            if not video_delivered:
                tg_client.send_message(
                    chat_id,
                    "The audio is yours, but alas, the video proved too gargantuan. ⚠️",
                    reply_to_id=message_id,
                    is_informative=False,
                )

            # Now that all delivery attempts are done, we can safely delete the confirmation message
            if confirmation_message_id:
                tg_client.delete_message(chat_id, confirmation_message_id)

        collection.update_one({"_id": task_id}, {"$set": {"status": status}})
        shutil.rmtree(task_dir, ignore_errors=True)
    except Exception as e:
        logger.exception(f"Critical error processing task {task_id}")
        tg_client.send_message(
            chat_id,
            f"A most unexpected complication has occurred. ⚠️\n{str(e)}",
            reply_to_id=message_id,
            is_informative=False,
        )
        collection.update_one({"_id": task_id}, {"$set": {"status": "failed"}})


def main():
    client = MongoClient(MONGODB_CONNECTION_STRING)
    db = client["ytbot"]
    collection = db["tasks"]

    # Atomically find and mark task as processing to avoid race conditions
    task = collection.find_one_and_update(
        {"status": "pending"}, {"$set": {"status": "processing"}}, return_document=True
    )

    if task:
        logger.info(f"Found pending task {task['_id']}. Starting processing...")
        process_task(task, collection)
    else:
        logger.info("No pending tasks found. Exiting.")


if __name__ == "__main__":
    main()
