import time
import math
from abc import ABC, abstractmethod
from typing import Tuple, Optional
import numpy as np
import cv2

class BaseVideoSource(ABC):
    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame from video source. Returns (success, frame_bgr)."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release video source resources."""
        pass


class FileVideoSource(BaseVideoSource):
    """Video source for pre-recorded video files (mp4, avi, etc.)."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.cap = cv2.VideoCapture(file_path)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.cap or not self.cap.isOpened():
            return False, None
        ret, frame = self.cap.read()
        if not ret:
            # Loop video file for continuous simulation
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
        return ret, frame

    def release(self) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.release()


class WebcamVideoSource(BaseVideoSource):
    """Video source for webcam or video capture device."""
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
        # Horizontal road
        cv2.rectangle(frame, (0, self.height // 2 - 50), (self.width, self.height // 2 + 50), (80, 80, 80), -1)
        # Vertical road
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


def create_video_source(source_str: str) -> BaseVideoSource:
    """Factory function creating appropriate VideoSource implementation."""
    if source_str.isdigit():
        return WebcamVideoSource(int(source_str))
    elif source_str.startswith("webcam"):
        return WebcamVideoSource(0)
    elif source_str.lower() in ["synthetic", "mock", "sim"]:
        return SyntheticVideoSource()
    else:
        return FileVideoSource(source_str)
