import logging
import os

import yt_dlp

logger = logging.getLogger(__name__)


class YoutubeDownloader:
    def __init__(self, cookies_path: str = None):
        self.cookies_path = cookies_path

    def extract_info(self, url: str):
        opts = {
            "format": "best",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": self.cookies_path,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def download(
        self, url: str, output_path: str, format_id: str, is_video: bool = False
    ):
        """
        Downloads a file from YouTube.
        """
        ydl_opts = {
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "format": format_id,
            "merge_output_format": "mp4",
            "cookiefile": self.cookies_path,
        }

        if is_video:
            ydl_opts["postprocessor_args"] = {
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
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-movflags",
                    "+faststart",
                ],
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # yt-dlp sometimes changes the filename slightly (e.g. adding .f137.mp4)
        # We need to find the actual file downloaded.
        dir_name = os.path.dirname(output_path)
        base_name = os.path.basename(output_path)

        if os.path.exists(output_path):
            return output_path

        for f in os.listdir(dir_name):
            if f.startswith(base_name):
                return os.path.join(dir_name, f)

        raise FileNotFoundError(f"Could not find downloaded file for {url}")
