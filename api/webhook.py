import json
import os
import re
from http.server import BaseHTTPRequestHandler

import requests
from pymongo import MongoClient

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
MONGODB_CONNECTION_STRING = os.environ.get("MONGODB_CONNECTION_STRING")


def send_telegram_message(chat_id, text, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id
    requests.post(url, json=payload)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data.decode("utf-8"))

        if "message" in update:
            msg = update["message"]
            text = msg.get("text") or msg.get("caption") or ""
            chat_id = msg["chat"]["id"]

            # Extract all YouTube URLs from the message
            links = re.findall(
                r"https?://(?:(?:www|m)\.)?(?:youtube\.com/(?:watch\?v=|shorts/|v/|embed/)|youtu\.be/)[^\s]+",
                text,
            )

            # Further clean the links to remove trailing punctuation or parameters that aren't part of the ID
            cleaned_links = []
            for link in links:
                # Remove trailing punctuation often captured by [^\s]+
                cleaned = re.sub(r"[.,!?;:]+$", "", link)
                cleaned_links.append(cleaned)

            if cleaned_links:
                try:
                    client = MongoClient(MONGODB_CONNECTION_STRING)
                    db = client["ytbot"]
                    collection = db["tasks"]
                    message_id = msg.get("message_id")

                    for link in cleaned_links:
                        # Avoid duplicates: check if task is already pending
                        exists = collection.find_one(
                            {"user_id": chat_id, "link": link, "status": "pending"}
                        )

                        if not exists:
                            collection.insert_one(
                                {
                                    "user_id": chat_id,
                                    "link": link,
                                    "status": "pending",
                                    "message_id": message_id,
                                }
                            )
                        else:
                            logger.info(f"Duplicate pending task ignored: {link}")

                    # Acknowledge the user with a summary of the discovered recordings
                    count = len(cleaned_links)
                    message = "Your request has been received"
                    if count > 1:
                        message = (
                            f"I have discovered {count} recordings in your message"
                        )
                    else:
                        message = "Your recording has been received"

                    send_telegram_message(
                        chat_id,
                        f"{message} and placed within our most distinguished queue. We shall attend to them post-haste. 🎩⏳",
                        reply_to_id=message_id,
                    )
                except Exception as e:
                    print(f"Error archiving request: {e}")
                    send_telegram_message(
                        chat_id,
                        "I regret to inform you that a complication has arisen whilst archiving your requests. Pray, try again shortly. ⚠️",
                        reply_to_id=msg.get("message_id"),
                    )

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"The webhook is dormant, awaiting its requests.")
