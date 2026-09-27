"""
EdgeFlow AI - Video Source Abstraction Layer.
Supports File streams, Webcams, Raspberry Pi Camera Module 3 / V4L2 devices, and Synthetic frames.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np
import cv2

logger = logging.getLogger("video-source")


class BaseVideoSource(ABC):
    """Abstract base class for all video frame ingestion sources."""
    
    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame from video source. Returns (success: bool, frame_bgr: np.ndarray)."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release video source resources."""
        pass


class PiCameraVideoSource(BaseVideoSource):
    """
    Hardware Video Source optimized for Raspberry Pi Camera Module 3 / USB camera devices.
    Configures standard V4L2 device parameters (buffer size, frame size, FPS).
    """
    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480, fps: float = 30.0):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = cv2.VideoCapture(device_index)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            # Reduce buffer size to 1 on Linux/Pi to eliminate frame lag
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            logger.info(f"Initialized Raspberry Pi Video Source on /dev/video{device_index} ({width}x{height} @ {fps}fps)")
        else:
            logger.warning(f"Could not open video device index {device_index}")

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        return ret, frame

    def release(self) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.release()
            logger.info(f"Released PiCamera source on device {self.device_index}")


class WebcamVideoSource(BaseVideoSource):
    """Video source for standard USB webcam or capture device."""
    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        self.cap = cv2.VideoCapture(device_id)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        return ret, frame

    def release(self) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.release()


class FileVideoSource(BaseVideoSource):
    """Video source for pre-recorded road traffic video files (mp4, avi, mkv)."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.cap = cv2.VideoCapture(file_path)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        if not ret:
            # Loop video file for continuous tabletop simulation
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        return ret, frame

    def release(self) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.release()


class SyntheticVideoSource(BaseVideoSource):
    """
    Synthetic video source generating artificial traffic camera frames.
    Renders road lanes and moving vehicle rectangles on a 640x480 canvas.
    Ideal for containerized CI/CD or headless environments without real camera feeds.
    """
    def __init__(self, width: int = 640, height: int = 480, fps: float = 10.0):
        self.width = width
        self.height = height
        self.fps = fps
        self.start_time = time.time()
        self.frame_count = 0

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        self.frame_count += 1
        t = (time.time() - self.start_time)

        # Create dark asphalt background
        frame = np.full((self.height, self.width, 3), 40, dtype=np.uint8)

        # Draw crossroad lanes
        # Horizontal road (East-West)
        cv2.rectangle(frame, (0, self.height // 2 - 50), (self.width, self.height // 2 + 50), (80, 80, 80), -1)
        # Vertical road (North-South)
        cv2.rectangle(frame, (self.width // 2 - 50, 0), (self.width // 2 + 50, self.height), (80, 80, 80), -1)

        # Draw lane center line dashes
        cv2.line(frame, (0, self.height // 2), (self.width, self.height // 2), (255, 255, 255), 2)
        cv2.line(frame, (self.width // 2, 0), (self.width // 2, self.height), (255, 255, 255), 2)

        # Draw moving synthetic vehicles (rectangles)
        # West to East stream
        for i in range(4):
            offset = (t * 80 + i * 140) % self.width
            vx = int(offset)
            vy = self.height // 2 + 15
            cv2.rectangle(frame, (vx, vy), (vx + 35, vy + 20), (0, 200, 255), -1)

        # North to South stream
        for i in range(3):
            offset = (t * 60 + i * 150) % self.height
            vx = self.width // 2 - 35
            vy = int(offset)
            cv2.rectangle(frame, (vx, vy), (vx + 20, vy + 35), (255, 100, 0), -1)

        return True, frame

    def release(self) -> None:
        pass


def create_video_source(source_str: str, width: int = 640, height: int = 480) -> BaseVideoSource:
    """
    Factory function creating appropriate VideoSource implementation based on source string.
    Supports integer indexes (0, 1), /dev/video* paths, 'picamera', 'synthetic', or video files.
    """
    source_clean = str(source_str).strip()
    if source_clean.isdigit():
        return PiCameraVideoSource(int(source_clean), width=width, height=height)
    elif source_clean.startswith("/dev/video"):
        try:
            dev_idx = int(source_clean.replace("/dev/video", ""))
            return PiCameraVideoSource(dev_idx, width=width, height=height)
        except ValueError:
            return PiCameraVideoSource(0, width=width, height=height)
    elif source_clean.lower() in ("picamera", "rpi_camera", "camera_module3", "csi"):
        return PiCameraVideoSource(0, width=width, height=height)
    elif source_clean.startswith("webcam"):
        return WebcamVideoSource(0)
    elif source_clean.lower() in ["synthetic", "mock", "sim"]:
        return SyntheticVideoSource(width=width, height=height)
    else:
        return FileVideoSource(source_clean)
