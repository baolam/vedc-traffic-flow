"""
EdgeFlow AI - Raspberry Pi 5 & Edge Hardware Monitor.
Monitors onboard CPU temperature, system load, architecture, and thermal throttling status.
"""

import os
import platform
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("hardware-monitor")


def is_raspberry_pi() -> bool:
    """Detects whether the current host is a physical Raspberry Pi device."""
    model_file = "/sys/firmware/devicetree/base/model"
    if os.path.exists(model_file):
        try:
            with open(model_file, "r", encoding="utf-8", errors="ignore") as f:
                model = f.read().strip()
                return "Raspberry Pi" in model
        except Exception:
            pass
    return platform.machine() in ("aarch64", "armv7l") and os.path.exists("/sys/class/thermal/thermal_zone0/temp")


def get_cpu_temperature() -> float:
    """
    Reads the Raspberry Pi onboard CPU temperature in degrees Celsius (°C).
    Falls back to a nominal 45.0°C on desktop/simulator environments.
    """
    temp_file = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(temp_file):
        try:
            with open(temp_file, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                return round(float(raw) / 1000.0, 1)
        except Exception as e:
            logger.debug(f"Failed to read CPU thermal zone: {e}")
    return 45.0


def get_throttled_status() -> Optional[str]:
    """
    Checks if vcgencmd exists to query Raspberry Pi undervoltage / thermal throttling.
    """
    if is_raspberry_pi():
        try:
            import subprocess
            res = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=1.0)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
    return None


def get_hardware_diagnostics() -> Dict[str, Any]:
    """
    Returns a complete hardware diagnostic snapshot for telemetry reporting.
    """
    return {
        "is_raspberry_pi": is_raspberry_pi(),
        "device_model": platform.machine(),
        "system_platform": platform.platform(),
        "cpu_temp_c": get_cpu_temperature(),
        "throttled_status": get_throttled_status(),
        "python_version": platform.python_version()
    }
