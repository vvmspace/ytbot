import logging
import os

import yt_dlp

logger = logging.getLogger(__name__)


class YoutubeDownloader:
    def __init__(self, cookies_path: str = None, ffmpeg_path: str = None):
        self.cookies_path = cookies_path
        self.ffmpeg_path = ffmpeg_path

    def extract_info(self, url: str):
        opts = {
            "format": "best",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": self.cookies_path,
            "ffmpeg_location": self.ffmpeg_path,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    def select_formats(self, info, max_file_size):
        """
        Selects the best audio and video formats based on size limits and duration.
        Returns (best_a_fmt, best_v_fmt, best_v_details).
        """
        formats = info.get("formats", [])
        duration = info.get("duration", 0)

        def get_size(f):
            return f.get("filesize") or f.get("filesize_approx", float("inf"))

        # If duration > 10m, we will re-encode anyway, so we can afford a higher quality source
        HIGH_QUALITY_CAP = 500 * 1024 * 1024
        should_use_high_quality = duration > 600
        size_limit = HIGH_QUALITY_CAP if should_use_high_quality else max_file_size

        audio_m4a = [
            f
            for f in formats
            if f.get("acodec")
            and "mp4a" in f.get("acodec")
            and f.get("ext") == "m4a"
            and get_size(f) <= size_limit
        ]

        video_candidates = []
        # Combined MP4
        for f in [
            f
            for f in formats
            if f.get("vcodec") != "none"
            and f.get("acodec") != "none"
            and f.get("ext") == "mp4"
            and get_size(f) <= size_limit
        ]:
            video_candidates.append(
                {
                    "format_id": f["format_id"],
                    "width": f.get("width"),
                    "height": f.get("height"),
                    "size": get_size(f),
                }
            )

        # Video only + Best audio
        for v in [
            f
            for f in formats
            if f.get("vcodec")
            and "avc1" in f.get("vcodec")
            and f.get("acodec") == "none"
            and f.get("ext") == "mp4"
        ]:
            v_size = get_size(v)
            if v_size >= size_limit:
                continue
            best_a = max(
                [a for a in audio_m4a if get_size(a) <= (size_limit - v_size)],
                key=lambda x: x.get("abr", 0),
                default=None,
            )
            if best_a:
                video_candidates.append(
                    {
                        "format_id": f"{v['format_id']}+{best_a['format_id']}",
                        "width": v.get("width"),
                        "height": v.get("height"),
                        "size": v_size + get_size(best_a),
                    }
                )

        best_a_fmt = max(audio_m4a, key=lambda x: x.get("abr", 0), default=None)
        best_a_fmt = best_a_fmt["format_id"] if best_a_fmt else None

        best_v_fmt = None
        best_v_details = None
        if video_candidates:
            best_v_details = video_candidates[0]
            best_v_fmt = best_v_details["format_id"]

        return best_a_fmt, best_v_fmt, best_v_details

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
            "ffmpeg_location": self.ffmpeg_path,
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
