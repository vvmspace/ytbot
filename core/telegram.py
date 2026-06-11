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
            logger.info(
                f"Attempting to send message to {chat_id}: {text[:50]}... (reply_to={reply_to_id})"
            )
            self.bot.send_message(
                chat_id=chat_id, text=text, reply_to_message_id=reply_to_id
            )
            logger.info(f"Message sent successfully to {chat_id}")
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
            logger.info(
                f"Attempting to send video to {chat_id}. File: {file_path}, Duration: {duration}s"
            )
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
            logger.info(f"Video sent successfully to {chat_id}")
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
            logger.info(
                f"Attempting to send audio to {chat_id}. File: {file_path}, Duration: {duration}s"
            )
            with open(file_path, "rb") as audio_file:
                self.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    caption=caption,
                    reply_to_message_id=reply_to_id,
                    duration=duration,
                    timeout=60,
                )
            logger.info(f"Audio sent successfully to {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send audio to {chat_id}: {e}")
            raise e

    def delete_message(self, chat_id: int, message_id: int):
        try:
            logger.info(f"Attempting to delete message {message_id} for {chat_id}")
            self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Message {message_id} deleted successfully")
        except Exception as e:
            logger.error(f"Failed to delete message {message_id} for {chat_id}: {e}")
