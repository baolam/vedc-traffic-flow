"""
EdgeFlow AI - Raspberry Pi 5 & Edge Hardware Monitor.
Monitors onboard CPU temperature, system load, architecture, and thermal throttling status.
"""

import os
import re
import subprocess
import platform
import logging
from typing import Dict, Any, List, Optional

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


def get_cpu_temperature(fallback: Optional[float] = 45.0) -> Optional[float]:
    """
    Reads the Raspberry Pi onboard CPU temperature in degrees Celsius (°C).
    Returns `fallback` when there is no thermal zone (desktop/CI). The nominal 45.0 default is
    kept for existing callers; measurement reports pass fallback=None so nothing is invented.
    """
    temp_file = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(temp_file):
        try:
            with open(temp_file, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                return round(float(raw) / 1000.0, 1)
        except Exception as e:
            logger.debug(f"Failed to read CPU thermal zone: {e}")
    return fallback


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


# `vcgencmd get_throttled` bits (Raspberry Pi firmware). "occurred" bits stay set until reboot.
THROTTLE_FLAGS = {
    0: "under_voltage_now", 1: "freq_capped_now", 2: "throttled_now", 3: "soft_temp_limit_now",
    16: "under_voltage_occurred", 17: "freq_capped_occurred", 18: "throttled_occurred",
    19: "soft_temp_limit_occurred",
}


def decode_throttled(raw: Optional[str]) -> Optional[List[str]]:
    """'throttled=0x50005' -> flag names. [] means no under-voltage or throttling since boot."""
    if not raw or "=" not in raw:
        return None
    try:
        value = int(raw.split("=", 1)[1].strip(), 16)
    except ValueError:
        return None
    return [name for bit, name in sorted(THROTTLE_FLAGS.items()) if value & (1 << bit)]


def parse_ext5v(text: str) -> Optional[float]:
    """Parses `vcgencmd pmic_read_adc EXT5V_V` output, e.g. 'EXT5V_V volt(24)=5.13600000V'."""
    match = re.search(r"EXT5V_V\s+volt\(\d+\)=([0-9.]+)V", text or "")
    return float(match.group(1)) if match else None


def read_input_voltage() -> Optional[float]:
    """Pi 5 USB-C input voltage from the PMIC; None on other boards or off-Pi."""
    if not is_raspberry_pi():
        return None
    try:
        res = subprocess.run(["vcgencmd", "pmic_read_adc", "EXT5V_V"], capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_ext5v(res.stdout) if res.returncode == 0 else None


def read_board_model() -> Optional[str]:
    """e.g. 'Raspberry Pi 5 Model B Rev 1.0'; None when the device tree does not say."""
    try:
        with open("/sys/firmware/devicetree/base/model", "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip().rstrip("\x00") or None
    except OSError:
        return None


def read_mem_available_mb() -> Optional[float]:
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except (OSError, ValueError, IndexError):
        pass
    return None


def get_runtime_hardware() -> Dict[str, Any]:
    """Temperature, power and throttling evidence for health reports; None where not measurable."""
    raw = get_throttled_status()
    return {
        "cpu_temp_c": get_cpu_temperature(fallback=None),
        "throttled_raw": raw,
        "throttled_flags": decode_throttled(raw),
        "ext5v_v": read_input_voltage(),
        "load_1m": round(os.getloadavg()[0], 2) if hasattr(os, "getloadavg") else None,
        "mem_available_mb": read_mem_available_mb(),
    }
