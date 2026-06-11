import logging
import os

import telebot

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, api_key: str, debug: bool = False):
        self.bot = telebot.TeleBot(api_key)
        self.debug = debug

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_id: int = None,
        is_informative: bool = True,
    ):
        """
        Sends a message to the user.
        If is_informative is True, it only sends if debug mode is enabled.
        """
        if is_informative and not self.debug:
            return

        try:
            self.bot.send_message(
                chat_id=chat_id, text=text, reply_to_message_id=reply_to_id
            )
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

    def send_video(
        self,
        chat_id: int,
        file_path: str,
        caption: str,
        width: int = None,
        height: int = None,
        reply_to_id: int = None,
        duration: int = None,
    ):
        try:
            with open(file_path, "rb") as video_file:
                self.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=caption,
                    width=width,
                    height=height,
                    reply_to_message_id=reply_to_id,
                    duration=duration,
                    supports_streaming=True,
                    timeout=60,
                )
        except Exception as e:
            logger.error(f"Failed to send video to {chat_id}: {e}")
            raise e

    def send_audio(
        self,
        chat_id: int,
        file_path: str,
        caption: str,
        reply_to_id: int = None,
        duration: int = None,
    ):
        try:
            with open(file_path, "rb") as audio_file:
                self.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    caption=caption,
                    reply_to_message_id=reply_to_id,
                    duration=duration,
                    timeout=60,
                )
        except Exception as e:
            logger.error(f"Failed to send audio to {chat_id}: {e}")
            raise e
