from pathlib import Path
import re


def test_esp32_firmware_file_exists():
    ino_path = Path("src/hardware/firmware/esp32_signal_controller.ino")
    assert ino_path.exists(), "ESP32 Arduino firmware file must exist in src/hardware/firmware/"


def test_esp32_firmware_mqtt_topics():
    ino_path = Path("src/hardware/firmware/esp32_signal_controller.ino")
    content = ino_path.read_text(encoding="utf-8")

    # Verify MQTT subscriptions and publications adhere to architecture contract
    assert "edgeflow/v1/control/" in content or "edgeflow/v1/" in content
    assert "ack" in content.lower()
    assert "health" in content.lower()


def test_esp32_firmware_safety_delays():
    ino_path = Path("src/hardware/firmware/esp32_signal_controller.ino")
    content = ino_path.read_text(encoding="utf-8")

    # Verify clearance yellow and all-red are defined
    assert re.search(r"DURATION_YELLOW_MS|YELLOW_TIME|3000", content)
    assert re.search(r"DURATION_ALL_RED_MS|ALL_RED_TIME|2000", content)
    assert re.search(r"WATCHDOG|TIMEOUT|FALLBACK|FAILSAFE", content, re.IGNORECASE)


def test_schematic_and_pinout_doc():
    schematic_path = Path("src/hardware/schematic_and_pinout.md")
    assert schematic_path.exists()
    content = schematic_path.read_text(encoding="utf-8")
    assert "GPIO" in content
    assert "J1" in content
    assert "J2" in content
