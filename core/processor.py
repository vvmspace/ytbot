import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)


class MediaProcessor:
    def __init__(
        self,
        max_file_size: int,
        watermark_path: str = "watermark.png",
        ffmpeg_path: str = "ffmpeg",
        ffprobe_path: str = "ffprobe",
    ):
        self.max_file_size = max_file_size
        self.watermark_path = watermark_path
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path

    def get_duration(self, file_path: str) -> float:
        cmd = [
            self.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        return float(subprocess.check_output(cmd).decode().strip())

    def compress_audio(self, file_path: str, safe_name: str) -> str:
        """
        Compresses audio to fit within max_file_size.
        Returns the path to the compressed file.
        """
        initial_size = os.path.getsize(file_path)
        duration = self.get_duration(file_path)
        max_bitrate_bps = int((40 * 1024 * 1024 * 8) / duration)
        max_bitrate_kbps = max_bitrate_bps // 1000

        if max_bitrate_kbps >= 128:
            bitrate, channels = "128k", "2"
        elif max_bitrate_kbps >= 96:
            bitrate, channels = "96k", "1"
        elif max_bitrate_kbps >= 64:
            bitrate, channels = "64k", "1"
        else:
            bitrate, channels = f"{max_bitrate_kbps}k", "1"

        final_path = (
            file_path.replace(".m4a", "").replace(".webm", "").replace(".temp", "")
            + "_[compressed].mp3"
        )
        temp_output = final_path + ".tmp.mp3"
        tag_title = safe_name.replace("_", " ")

        logger.info(
            f"Re-encoding audio to MP3: {bitrate}, channels={channels}, duration={duration:.1f}s. "
            f"Initial size: {initial_size / (1024 * 1024):.2f}MB"
        )

        subprocess.run(
            [
                self.ffmpeg_path,
                "-y",
                "-i",
                file_path,
                "-b:a",
                bitrate,
                "-ac",
                str(channels),
                "-ar",
                "44100",
                "-id3v2_version",
                "3",
                "-metadata",
                "artist=@VVMPodcastsBot",
                "-metadata",
                f"title={tag_title}",
                temp_output,
            ],
            check=True,
            capture_output=True,
        )

        shutil.move(temp_output, final_path)
        final_size = os.path.getsize(final_path)
        logger.info(
            f"Audio compression complete. Final size: {final_size / (1024 * 1024):.2f}MB"
        )
        return final_path

    def compress_video(self, file_path: str) -> str:
        """
        Compresses video to fit within max_file_size with watermark.
        Returns the path to the compressed file.
        """
        initial_size = os.path.getsize(file_path)
        duration = self.get_duration(file_path)
        total_budget_bits = 40 * 1024 * 1024 * 8
        audio_bits = duration * 128 * 1000
        video_budget_bits = total_budget_bits - audio_bits

        logger.info(
            f"Starting video compression. Initial size: {initial_size / (1024 * 1024):.2f}MB, duration: {duration:.1f}s"
        )

        target_bitrate_kbps = (
            64
            if video_budget_bits <= 0
            else min(video_budget_bits // (duration * 1000), 2000)
        )

        if target_bitrate_kbps < 150:
            target_w = 320
            target_bitrate_kbps = max(target_bitrate_kbps, 100)
        else:
            target_w = 640

        # Watermark constraints: min 120px, max 1/4 of width
        wm_w = int(target_w * 0.15)
        wm_w = max(120, wm_w)
        wm_w = min(wm_w, int(target_w * 0.25))

        # Use lanczos scaling for high quality watermark
        filter_complex = (
            f"[0:v]scale={target_w}:-2[bg];"
            f"[1:v]scale={wm_w}:-1:flags=lanczos[wm];"
            f"[bg][wm]overlay=x=main_w-overlay_w-10:y=main_h-overlay_h-10:"
            f"enable='between(t,0,5)+between(t,{duration - 5},{duration})'"
        )

        final_path = (
            file_path.replace(".temp", "").replace(".mkv", "").replace(".webm", "")
            + "_[compressed].mp4"
        )
        temp_output = final_path + ".tmp.mp4"

        logger.info(
            f"Two-pass encoding video. Bitrate: {target_bitrate_kbps}k, Width: {target_w}px, Preset: slower"
        )

        # Pass 1
        subprocess.run(
            [
                self.ffmpeg_path,
                "-y",
                "-i",
                file_path,
                "-i",
                self.watermark_path,
                "-c:v",
                "libx264",
                "-b:v",
                f"{target_bitrate_kbps}k",
                "-preset",
                "slower",
                "-filter_complex",
                filter_complex,
                "-an",
                "-f",
                "mp4",
                "-pass",
                "1",
                "/dev/null" if os.name != "nt" else "NUL",
            ],
            check=True,
            capture_output=True,
        )

        # Pass 2
        subprocess.run(
            [
                self.ffmpeg_path,
                "-y",
                "-i",
                file_path,
                "-i",
                self.watermark_path,
                "-c:v",
                "libx264",
                "-b:v",
                f"{target_bitrate_kbps}k",
                "-preset",
                "slower",
                "-filter_complex",
                filter_complex,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                temp_output,
            ],
            check=True,
            capture_output=True,
        )

        shutil.move(temp_output, final_path)

        # Save screenshot at 2 seconds
        try:
            subprocess.run(
                [
                    self.ffmpeg_path,
                    "-y",
                    "-ss",
                    "2",
                    "-i",
                    final_path,
                    "-vframes",
                    "1",
                    "last.png",
                ],
                check=True,
                capture_output=True,
            )
            logger.info("Saved screenshot last.png")
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")

        final_size = os.path.getsize(final_path)
        logger.info(
            f"Video compression complete. Final size: {final_size / (1024 * 1024):.2f}MB"
        )

        # Clean up ffmpeg logs
        for f in os.listdir("."):
            if f.startswith("ffmpeg2pass"):
                os.remove(f)

        return final_path

    def process(self, file_path: str, media_type: str, safe_name: str = None) -> tuple:
        """
        Main entry point for processing. Re-encodes if file is too large
        or if it's a video longer than 10 minutes (to apply watermark).
        Returns a tuple of (final_path, duration).
        """
        duration = self.get_duration(file_path)
        file_size = os.path.getsize(file_path)

        if media_type == "video":
            # Apply watermark if video is > 10 minutes OR exceeds size limit
            if duration > 600 or file_size > self.max_file_size:
                final_path = self.compress_video(file_path)
                return final_path, duration

            # Otherwise, just ensure extension is correct and move
            final_path = (
                file_path.replace(".temp", "")
                .replace(".mkv", ".mp4")
                .replace(".webm", ".mp4")
            )
            if file_path != final_path:
                shutil.move(file_path, final_path)
            return final_path, duration

        if media_type == "audio":
            if file_size > self.max_file_size:
                final_path = self.compress_audio(file_path, safe_name)
            else:
                final_path = file_path.replace(".temp", "")  # simplified
            return final_path, duration

        return file_path, duration
