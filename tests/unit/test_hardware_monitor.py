import os
import platform
import pytest
from unittest.mock import patch, mock_open

from services.vision.hardware_monitor import (
    is_raspberry_pi,
    get_cpu_temperature,
    get_throttled_status,
    get_hardware_diagnostics,
)


def test_get_hardware_diagnostics_structure():
    diag = get_hardware_diagnostics()
    assert isinstance(diag, dict)
    assert "is_raspberry_pi" in diag
    assert "device_model" in diag
    assert "system_platform" in diag
    assert "cpu_temp_c" in diag
    assert "throttled_status" in diag
    assert "python_version" in diag
    assert isinstance(diag["cpu_temp_c"], (int, float))


def test_get_cpu_temperature_default_fallback():
    # If thermal zone file does not exist, should return nominal 45.0
    with patch("os.path.exists", return_value=False):
        temp = get_cpu_temperature()
        assert temp == 45.0


def test_get_cpu_temperature_reads_file():
    # Mock thermal zone file with millidegrees (e.g. 52340 -> 52.3)
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="52340\n")):
            temp = get_cpu_temperature()
            assert temp == 52.3


def test_is_raspberry_pi_detection():
    # When device tree model has Raspberry Pi string
    with patch("os.path.exists", side_effect=lambda path: path == "/sys/firmware/devicetree/base/model"):
        with patch("builtins.open", mock_open(read_data="Raspberry Pi 5 Model B Rev 1.0\x00")):
            assert is_raspberry_pi() is True

    # When device tree model has non-pi string
    with patch("os.path.exists", return_value=False):
        with patch("platform.machine", return_value="x86_64"):
            assert is_raspberry_pi() is False
