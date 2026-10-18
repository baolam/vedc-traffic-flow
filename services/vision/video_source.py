"""
EdgeFlow AI - Video Source Abstraction Layer.
Supports File streams, Webcams, Raspberry Pi Camera Module 3 / V4L2 devices, and Synthetic frames.
"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
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


def pick_full_fov_mode(sensor_modes: List[Dict[str, Any]], min_fps: float) -> Optional[Dict[str, Any]]:
    """
    Smallest sensor mode that sees the whole sensor (largest crop_limits area) at >= min_fps.
    For a 1280x720 output libcamera otherwise picks Camera Module 3's 1536x864 mode, a centre crop
    (768,432)/3072x1728 that loses a third of the Wide lens' view in each direction.
    If no full-FOV mode reaches min_fps, the fastest full-FOV mode is returned: coverage matters more.
    """
    modes = [m for m in sensor_modes if m.get("crop_limits") and m.get("size")]
    if not modes:
        return None
    area = lambda m: m["crop_limits"][2] * m["crop_limits"][3]  # noqa: E731
    full = [m for m in modes if area(m) == max(area(m) for m in modes)]
    fast = [m for m in full if m.get("fps", 0) >= min_fps]
    if fast:
        return min(fast, key=lambda m: m["size"][0] * m["size"][1])
    return max(full, key=lambda m: m.get("fps", 0))


class Picamera2VideoSource(BaseVideoSource):
    """
    Raspberry Pi Camera Module 3 (CSI) through libcamera/Picamera2.

    On Raspberry Pi 5 the CSI camera is only reachable through libcamera; OpenCV's
    V4L2 backend cannot read it via cv2.VideoCapture(0). Requires the Raspberry Pi OS
    package python3-picamera2 (use a venv created with --system-site-packages).

    lens_position: fixed focus in dioptres (1/metres); None keeps continuous autofocus.
    The camera hangs ~0.5 m above the tabletop, so ~2.0 is a sane starting point.
    flicker_period_us: 10000 cancels 50 Hz mains flicker (Vietnam); 0 disables.
    """
    def __init__(self, width: int = 640, height: int = 480, fps: float = 30.0,
                 lens_position: Optional[float] = None, flicker_period_us: int = 10000):
        from picamera2 import Picamera2  # Raises ImportError off-Pi: no silent fallback.

        self.width = width
        self.height = height
        self.camera = Picamera2()
        mode = pick_full_fov_mode(list(getattr(self.camera, "sensor_modes", None) or []), fps)
        # Only pin the mode when the camera lists its modes; otherwise keep libcamera's choice.
        extra = {"sensor": {"output_size": tuple(mode["size"]), "bit_depth": mode["bit_depth"]}} if mode else {}
        # "RGB888" in Picamera2 is BGR byte order in memory, i.e. what OpenCV expects.
        config = self.camera.create_video_configuration(
            main={"size": (width, height), "format": "RGB888"},
            controls={"FrameRate": min(fps, mode["fps"]) if mode else fps},
            buffer_count=2,
            **extra,
        )
        self.camera.configure(config)
        if mode:
            logger.info(f"Sensor mode {mode['size'][0]}x{mode['size'][1]} @ {mode['fps']:.0f} fps, "
                        f"crop {tuple(mode['crop_limits'])} (full field of view)")
        self.camera.start()
        self._apply_controls(lens_position, flicker_period_us)
        logger.info(f"Initialized Picamera2 CSI source ({width}x{height} @ {fps}fps, "
                    f"lens_position={lens_position}, flicker_period_us={flicker_period_us})")

    def _apply_controls(self, lens_position: Optional[float], flicker_period_us: int) -> None:
        available = self.camera.camera_controls
        controls = {}
        if lens_position is not None and "LensPosition" in available:
            from libcamera import controls as lc
            controls["AfMode"] = lc.AfModeEnum.Manual
            controls["LensPosition"] = float(lens_position)
        if flicker_period_us > 0 and "AeFlickerPeriod" in available:
            from libcamera import controls as lc
            controls["AeFlickerMode"] = lc.AeFlickerModeEnum.Manual
            controls["AeFlickerPeriod"] = int(flicker_period_us)
        if controls:
            self.camera.set_controls(controls)

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        try:
            frame = self.camera.capture_array("main")
        except Exception as e:
            logger.error(f"Picamera2 capture failed: {e}")
            return False, None
        if frame is None:
            return False, None
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = frame[:, :, :3]
        return True, frame

    def release(self) -> None:
        try:
            self.camera.stop()
            self.camera.close()
        except Exception as e:
            logger.warning(f"Picamera2 release failed: {e}")


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


def create_video_source(source_str: str, width: int = 640, height: int = 480,
                        lens_position: Optional[float] = None,
                        flicker_period_us: int = 10000) -> BaseVideoSource:
    """
    Factory function creating appropriate VideoSource implementation based on source string.
    Supports integer indexes (0, 1) and /dev/video* paths (USB/V4L2 cameras), 'picamera'
    (CSI Camera Module 3 via Picamera2), 'synthetic', or video files.
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
    elif source_clean.lower() in ("picamera", "picamera2", "rpi_camera", "camera_module3", "csi"):
        return Picamera2VideoSource(width=width, height=height, lens_position=lens_position,
                                    flicker_period_us=flicker_period_us)
    elif source_clean.startswith("webcam"):
        return WebcamVideoSource(0)
    elif source_clean.lower() in ["synthetic", "mock", "sim"]:
        return SyntheticVideoSource(width=width, height=height)
    else:
        return FileVideoSource(source_clean)
