import json
import os
from http.server import BaseHTTPRequestHandler

import requests
from pymongo import MongoClient

TELEGRAM_API_KEY = os.environ.get("TELEGRAM_API_KEY")
MONGODB_CONNECTION_STRING = os.environ.get("MONGODB_CONNECTION_STRING")


def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_API_KEY}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        update = json.loads(post_data.decode("utf-8"))

        if "message" in update and "text" in update["message"]:
            chat_id = update["message"]["chat"]["id"]
            text = update["message"]["text"]

            if "youtube.com" in text or "youtu.be" in text:
                try:
                    # Archive the request in MongoDB
                    client = MongoClient(MONGODB_CONNECTION_STRING)
                    db = client["ytbot_db"]
                    collection = db.ytbot

                    collection.insert_one(
                        {"user_id": chat_id, "link": text, "status": "pending"}
                    )

                    # Acknowledge the user with utmost grace
                    send_telegram_message(
                        chat_id,
                        "Your request has been received and placed within our most distinguished queue. We shall attend to it post-haste. 🎩⏳",
                    )
                except Exception as e:
                    print(f"Error archiving request: {e}")
                    send_telegram_message(
                        chat_id,
                        "I regret to inform you that a complication has arisen whilst archiving your request. Pray, try again shortly. ⚠️",
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
