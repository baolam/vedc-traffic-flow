"""Sinh 3.3_kien_truc/EdgeFlow_3.3_kien_truc.drawio (4 trang) cho mục 3.3 của báo cáo.

Nội dung bám code trên nhánh main + phần chưa commit (ngày 10/10/2026):
  - firmware: src/hardware/firmware/esp32_signal_controller.ino
  - vision:   services/vision/*.py
  - máy chủ điều phối: docker-compose.yml, services/{graph-control,api,dashboard}
Ngày 11/10 sửa theo góp ý của Bảo Lâm (ảnh trong _ghi_chu/): vẽ cho triển khai thực tế, không nhắc laptop;
sa bàn là một khu vực giao thông bất kỳ; API đã theo dõi MQTT (origin/main a3f5aee); Pi không dùng Ethernet.

CẢNH BÁO: chạy lại script sẽ GHI ĐÈ file .drawio. Khi đội đã sửa trên draw.io thì
file .drawio là bản gốc, đừng chạy lại.
"""
from __future__ import annotations

import sys
from pathlib import Path

from drawio_lib import (FLOW, TIER, Page, box_style, container_style, edge_style, label, style,
                        write_drawio)

OUT = Path(__file__).resolve().parents[1] / "3.3_kien_truc" / "EdgeFlow_3.3_kien_truc.drawio"

JUMP = {"jumpStyle": "arc", "jumpSize": 10}


def hw(tier: str, **kw) -> str:
    """Khối phần cứng: tô màu nền của tầng."""
    return box_style(tier, white=False, **kw)


def legend(p: Page, x: int, y: int, items: list[tuple[str, str, bool, bool]]) -> None:
    for i, (flow, text, dashed, dotted) in enumerate(items):
        lx = x + i * 320
        extra = {"dashPattern": "2 3"} if dotted else None
        p.free_edge(f"lg{i}", (lx, y), (lx + 46, y), "",
                    edge_style(flow, dashed=dashed or dotted, extra=extra, end="oval" if dotted else "block"))
        p.text(f"lgt{i}", lx + 54, y - 12, 250, 24, text, size=12, color="#333333")


# ---------------------------------------------------------------- H3.1 Sơ đồ khối tổng thể
def page_block() -> Page:
    p = Page("H3.1 Sơ đồ khối tổng thể", 1700, 1040)

    # Khu vực giao thông được quản lý: đầu vào và đầu ra của vòng kín. Sa bàn J1 – J2 chỉ là một trường hợp;
    # graph-control đọc topology theo EDGEFLOW_TOPOLOGY nên đổi khu vực = đổi file topology trong contracts/.
    world = p.vertex("world", 40, 30, 1620, 130,
                     "KHU VỰC GIAO THÔNG QUẢN LÝ — mạng lưới đường bất kỳ, mô tả bằng đồ thị topology "
                     "(nút = ngã tư, cạnh = đoạn đường) · sa bàn thử nghiệm: 2 ngã tư J1 – J2",
                     container_style("world"))
    j1 = p.vertex("w_j1", 180, 45, 260, 60, label("Ngã tư J1", "4 hướng vào: Bắc · Nam · Đông · Tây"),
                  box_style("world"), world)
    lk = p.vertex("w_link", 500, 45, 260, 60, label("Đoạn nối J1 ⇄ J2", "hàng đợi hạ lưu lan ngược lên thượng lưu"),
                  box_style("world"), world)
    j2 = p.vertex("w_j2", 820, 45, 260, 60, label("Ngã tư J2", "4 hướng vào: Bắc · Nam · Đông · Tây"),
                  box_style("world"), world)
    jn = p.vertex("w_jn", 1140, 45, 300, 60, label("Ngã tư Jn (mở rộng)", "thêm nút vào topology<br>"
                                                                             "+ 1 camera + 1 ESP32 với NODE_ID mới"),
                  box_style("world", dashed=True), world)
    plain = edge_style("physical", end="none", width=1.4)
    p.edge("w_e1", j1, lk, "", plain)
    p.edge("w_e2", lk, j2, "", plain)
    p.edge("w_e3", j2, jn, "…", edge_style("physical", end="none", width=1.4, dashed=True, size=14))

    # Raspberry Pi 5
    pi = p.vertex("pi", 40, 230, 400, 560, "RASPBERRY PI 5 (4 GB) — AI TẠI BIÊN", container_style("edge_ai"))
    steps = [
        ("p_cam", label("2 × Camera Module 3 Wide", "trên trụ J1 và J2 · 120° · cáp CSI 22→15 pin 1 m"), True),
        ("p_cap", label("Thu ảnh (Picamera2)", "toàn khung → 1280×720 · CAM0 → J1, CAM1 → J2<br>"
                                                "(đọc 2 camera trên 1 Pi: đang phát triển)"), False),
        ("p_det", label("Phát hiện xe — YOLO11n", "ONNX qua OpenCV DNN, CPU 4× Cortex-A76"), False),
        ("p_roi", label("Gán xe vào ROI từng hướng", "mỗi camera một nút: J1_*_IN · J2_*_IN"), False),
        ("p_win", label("Tổng hợp mỗi 1 giây", "trung vị hàng đợi · lưu lượng · độ tin cậy"), False),
        ("p_pub", label("MQTT client", "gửi telemetry, health, LWT · kiểm JSON Schema"), False),
    ]
    ids = []
    for i, (cid, val, is_hw) in enumerate(steps):
        sty = hw("edge_ai", bold=False) if is_hw else box_style("edge_ai")
        ids.append(p.vertex(cid, 25, 50 + i * 82, 350, 62, val, sty, pi))
    for a, b in zip(ids, ids[1:]):
        p.edge(f"pe_{a}", a, b, "", edge_style("observe", width=1.5))

    # Máy chủ điều phối của khu vực
    lap = p.vertex("lap", 580, 230, 520, 560, "MÁY CHỦ ĐIỀU PHỐI KHU VỰC — DOCKER COMPOSE", container_style("control"))
    broker = p.vertex("l_broker", 25, 50, 470, 70,
                      label("MQTT Broker — Eclipse Mosquitto 2.0", "cổng 1883 · mọi topic có tiền tố edgeflow/v1/"),
                      hw("network"), lap)
    gc = p.vertex("l_gc", 25, 210, 225, 120,
                  label("Graph-Control", "điều khiển trên đồ thị mạng lưới<br><b>MaxPressure · EdgeFlow</b><br>"
                                         "(Fixed-Time, MaxQueue làm mốc)"), box_style("control"), lap)
    api = p.vertex("l_api", 270, 210, 225, 120,
                   label("API — FastAPI :8000", "trạng thái trực tiếp từ MQTT<br>topology · thí nghiệm<br>"
                                                "đổi bộ điều khiển"),
                   box_style("control"), lap)
    p.vertex("l_contracts", 25, 390, 225, 70,
             label("contracts/", "JSON Schema + topology khu vực<br>dùng chung cho mọi khối"),
             box_style("shared", dashed=True), lap)
    dash = p.vertex("l_dash", 270, 390, 225, 70,
                    label("Dashboard — React :3000", "giám sát kiểu trung tâm IOC"), box_style("control"), lap)
    p.vertex("l_sumo", 25, 480, 470, 56,
             label("Mô phỏng SUMO (tùy chọn)", "cùng hợp đồng dữ liệu · thử bộ điều khiển trước khi áp dụng"),
             box_style("shared", dashed=True), lap)

    # ESP32
    esp = p.vertex("esp", 1240, 230, 420, 560, "2× ESP32 NodeMCU-32S — NÚT ĐÈN", container_style("actuate"))
    esp_body = ("• kiểm lệnh: nút, pha, hạn, min green<br>• đổi pha an toàn:<br>&nbsp;&nbsp;vàng 3 s → đỏ toàn phần 2 s"
                "<br>• mất lệnh &gt; 5 s → tự chạy 15 s/pha<br>• gửi ACK + health")
    e1 = p.vertex("e1", 15, 50, 220, 220, label("ESP32 J1", esp_body), box_style("actuate", align="left"), esp)
    led1 = p.vertex("e1_led", 250, 50, 155, 130,
                    label("Cụm đèn 4 mặt", "treo trên trụ<br>Bắc + Nam: GPIO 23/22/21<br>Đông + Tây: GPIO 19/18/5"),
                    hw("actuate"), esp)
    p.vertex("e1_stop", 250, 195, 155, 75, label("Nút safe-stop", "GPIO 4 · active-LOW"), hw("safety"), esp)
    e2 = p.vertex("e2", 15, 300, 220, 220,
                  label("ESP32 J2", "cùng firmware, NODE_ID = J2<br>chạy độc lập với J1:<br>J1 mất mạng thì J2<br>"
                                    "vẫn tự giữ an toàn"), box_style("actuate", align="left"), esp)
    p.vertex("e2_led", 250, 300, 155, 130,
             label("Cụm đèn 4 mặt", "treo trên trụ<br>Bắc + Nam: GPIO 23/22/21<br>Đông + Tây: GPIO 19/18/5"), hw("actuate"), esp)
    p.vertex("e2_stop", 250, 445, 155, 75, label("Nút safe-stop", "GPIO 4 · active-LOW"), hw("safety"), esp)
    for a, b in (("e1", "e1_led"), ("e2", "e2_led")):
        p.edge(f"ee_{a}", a, b, "", edge_style("command", width=1.5), exit_=(1, 0.3), entry=(0, 0.5))

    # Router (tầng mạng vật lý)
    router = p.vertex("router", 40, 860, 1620, 70,
                      label("MẠNG LAN RIÊNG CỦA KHU VỰC — router Wi-Fi 2.4 GHz, không cần Internet",
                            "mọi thiết bị chỉ trao đổi qua MQTT · IP cố định bằng DHCP reservation · "
                            "tắt client isolation", title_size=14), hw("network"))

    # --- Luồng logic MQTT
    obs, cmd, fb = edge_style("observe"), edge_style("command"), edge_style("feedback")
    p.edge("f_tel", "p_pub", broker, "telemetry/{node}<br>1 lần/giây/nút", obs,
           exit_=(1, 0.5), entry=(0, 0.25), points=[(510, 721), (510, 297.5)], label_pos=-0.3)
    p.edge("f_hph", broker, "p_win", "health/{node}<br>pha đèn thực tế", edge_style("feedback", extra=JUMP),
           exit_=(0, 0.75), entry=(1, 0.5), points=[(545, 332.5), (545, 639)], label_pos=-0.25)
    p.edge("f_gc_in", broker, gc, "telemetry/+", obs, exit_=(0.16, 1), entry=(0.333, 1 - 1),
           label_offset=(-40, 0))
    p.edge("f_gc_out", gc, broker, "command", cmd, exit_=(0.69, 0), entry=(0.33, 1), label_offset=(34, 0))
    p.edge("f_api", broker, api, "theo dõi edgeflow/v1/#<br>telemetry · command · ack", obs,
           exit_=(0.809, 1), entry=(0.6, 0), label_offset=(0, 0))
    p.edge("f_rest", api, dash, "WebSocket · REST", edge_style("physical", both=True, width=1.4), exit_=(0.5, 1),
           entry=(0.5, 0))
    p.edge("f_cmd1", broker, e1, "control/{node}/command", cmd, exit_=(1, 0.3), entry=(0, 0.2),
           points=[(1160, 301), (1160, 324)], label_pos=-0.55, label_offset=(46, -14))
    p.edge("f_cmd2", broker, e2, "", cmd, exit_=(1, 0.3), entry=(0, 0.2), points=[(1160, 301), (1160, 574)])
    fbj = edge_style("feedback", extra=JUMP)
    p.edge("f_ack1", e1, broker, "", fbj, exit_=(0, 0.6), entry=(1, 0.75), points=[(1200, 412), (1200, 332.5)])
    p.edge("f_ack2", e2, broker, "control/{node}/ack<br>health/{node}", fbj, exit_=(0, 0.6), entry=(1, 0.75),
           points=[(1200, 662), (1200, 332.5)], label_pos=-0.62)

    # --- Vòng kín vật lý
    p.edge("f_see", world, "p_cam", "camera trên trụ mỗi ngã tư quan sát dòng xe", edge_style("observe", width=2.2),
           exit_=(0.199, 1), entry=(0.85, 0), label_offset=(-82, 0))
    p.edge("f_act", led1, world, "đèn điều tiết dòng xe", edge_style("command", width=2.2),
           exit_=(0.5, 0), entry=(0.943, 1), label_offset=(-70, 0))

    # --- Liên kết vật lý tới router
    phys = edge_style("physical", dashed=True, both=True, width=1.4, end="oval",
                      extra={"dashPattern": "2 3", "startSize": 5, "endSize": 5})
    p.edge("n_pi", pi, router, "Wi-Fi", phys, exit_=(0.5, 1), entry=(0.1235, 0))
    p.edge("n_lap", lap, router, "Wi-Fi hoặc LAN", phys, exit_=(0.5, 1), entry=(0.4938, 0))
    p.edge("n_esp", esp, router, "Wi-Fi 2.4 GHz", phys, exit_=(0.5, 1), entry=(0.8704, 0))

    legend(p, 60, 985, [("observe", "Dữ liệu quan sát (telemetry)", False, False),
                        ("command", "Lệnh điều khiển (command)", False, False),
                        ("feedback", "Phản hồi (ACK, health)", False, False),
                        ("physical", "Kết nối mạng vật lý", False, True)])
    return p


# ---------------------------------------------------------------- H3.2 Phần cứng và đấu nối
def page_hardware() -> Page:
    p = Page("H3.2 Phần cứng và đấu nối", 1700, 980)

    # Cột A: nguồn
    ac = p.vertex("a_ac", 40, 60, 300, 56, label("Ổ cắm 220 V AC"), box_style("world"))
    pipsu = p.vertex("a_pipsu", 40, 200, 300, 70, label("Nguồn Raspberry Pi 27 W", "USB-C PD · 5,1 V / 5 A"),
                     hw("power"))
    adp = p.vertex("a_adp", 40, 380, 300, 70, label("Adapter 5 V / 4 A", "đầu DC 5.5 × 2.1 mm"), hw("power"))
    jack = p.vertex("a_jack", 40, 490, 300, 60, label("Jack DC cái → domino", "đường 5 V chung cho 2 nút"),
                    hw("power"))
    prot = p.vertex("a_prot", 40, 590, 300, 70,
                    label("Bảo vệ nguồn", "cầu chì PTC 0,5–1 A + diode Schottky 1N5819<br>(sụt áp ~0,3 V)"),
                    hw("power"))
    p.vertex("a_note", 40, 720, 300, 150,
             label("Hai miền nguồn tách riêng",
                   "• Pi 5 dùng nguồn USB-C 27 W riêng.<br>• 2 ESP32 và 8 module đèn dùng adapter 5 V.<br>"
                   "• GND chung giữa 2 ESP32.<br>• Rút nguồn 5 V ngoài khi đang nạp firmware qua micro-USB.",
                   title_size=12), box_style("shared", dashed=True, align="left"))
    pw = edge_style("power", width=2)
    p.edge("pw1", ac, pipsu, "", pw)
    p.edge("pw2", ac, adp, "", pw, exit_=(0, 0.5), entry=(0, 0.5), points=[(20, 88), (20, 415)])
    p.edge("pw3", adp, jack, "", pw)
    p.edge("pw4", jack, prot, "", pw)

    # Cột B: camera, Pi, router, máy chủ điều phối
    cam = p.vertex("b_cam", 440, 60, 360, 80,
                   label("2 × Camera Module 3 Wide (SC0874)", "trên trụ J1 và J2 · Sony IMX708 12 MP · 120° chéo"),
                   hw("edge_ai"))
    pi = p.vertex("b_pi", 440, 230, 360, 120,
                  label("Raspberry Pi 5 — 4 GB", "BCM2712 · 4× Cortex-A76 2,4 GHz<br>"
                                                "microSD 64 GB · tản nhiệt + quạt 5 V · vỏ ABS"), hw("edge_ai"))
    router = p.vertex("b_router", 440, 480, 360, 90,
                      label("Router Wi-Fi 2.4 GHz", "LAN riêng · DHCP reservation · tắt client isolation"),
                      hw("network"))
    lap = p.vertex("b_lap", 440, 685, 360, 80,
                   label("Máy chủ điều phối khu vực", "Docker: Mosquitto · Graph-Control · API · Dashboard"),
                   hw("control"))
    phys = edge_style("physical", width=1.6)
    p.edge("b1", cam, pi, "2 cáp FPC CSI 22 → 15 pin, dài 1 m<br>(CAM0 → J1 · CAM1 → J2)", phys)
    p.edge("b2", pipsu, pi, "USB-C", pw, exit_=(1, 0.5), entry=(0, 0.5))
    p.edge("b3", pi, router, "Wi-Fi", edge_style("physical", both=True, dashed=True,
                                                   extra={"dashPattern": "2 3"}))
    p.edge("b4", router, lap, "Wi-Fi hoặc LAN", edge_style("physical", both=True), label_pos=-0.5,
           label_offset=(62, -6))

    # Cột C: ESP32 J1 với các chân
    esp = p.vertex("c_esp", 900, 60, 360, 720,
                   "ESP32 NodeMCU-32S — NÚT J1<br><span style=\"font-weight:normal;font-size:11px\">"
                   "ESP-WROOM-32 · CH340 · micro-USB</span>", container_style("actuate"))
    p.text("c_info", 15, 70, 170, 330,
           "<b>Vi điều khiển</b><br>Xtensa LX6 2 nhân 240 MHz<br>520 KB SRAM · 4 MB flash<br>"
           "Wi-Fi 802.11 b/g/n 2.4 GHz<br><br><b>Firmware</b><br>"
           "<span style=\"font-family:Menlo,monospace;font-size:10px\">esp32_signal_<br>controller.ino</span><br>"
           "PlatformIO · env J1 / J2<br><br><b>Mức logic</b><br>GPIO 3,3 V<br><br><b>Đèn</b><br>Bắc và Nam cùng pha nên mắc "
           "song song trên 3 chân; Đông và Tây cũng vậy. ~6 mA/LED ở 3,3 V, ~12 mA/chân", size=11, color="#2F2F2F",
           parent=esp)
    pin = lambda tier, **kw: box_style(tier, size=11, **kw)  # noqa: E731
    ns = p.vertex("pin_ns", 200, 60, 150, 50, label("GPIO 23 / 22 / 21", "R / Y / G — pha Bắc–Nam", title_size=12),
                  pin("actuate"), esp)
    ew = p.vertex("pin_ew", 200, 200, 150, 50, label("GPIO 19 / 18 / 5", "R / Y / G — pha Đông–Tây",
                                                       title_size=12), pin("actuate"), esp)
    stp = p.vertex("pin_stop", 200, 340, 150, 50, label("GPIO 4", "safe-stop · INPUT_PULLUP", title_size=12),
                   pin("safety"), esp)
    p.vertex("pin_led", 200, 440, 150, 50, label("GPIO 2", "LED trạng thái trên board", title_size=12),
             pin("actuate", dashed=True), esp)
    wifi = p.vertex("pin_wifi", 10, 440, 150, 50, label("Wi-Fi (STA)", "MQTT tới broker", title_size=12),
                    pin("network"), esp)
    vin = p.vertex("pin_vin", 10, 540, 150, 50, label("VIN 5 V · GND", "nguồn từ adapter", title_size=12),
                   pin("power"), esp)
    p.vertex("pin_usb", 10, 640, 150, 50, label("micro-USB (CH340)", "nạp firmware · log TRACE",
                                                       title_size=12), pin("shared"), esp)

    p.edge("c1", router, wifi, "Wi-Fi 2.4 GHz", edge_style("physical", both=True, dashed=True,
                                                            extra={"dashPattern": "2 3"}))
    p.edge("c2", prot, vin, "5 V · GND chung", edge_style("power", width=2, extra=JUMP), exit_=(1, 0.5),
           entry=(0, 0.5), label_pos=0.65)

    esp2 = p.vertex("c_esp2", 900, 830, 360, 90,
                    label("ESP32 NodeMCU-32S — NÚT J2", "đấu nối giống hệt J1:<br>cụm đèn 4 mặt trên trụ J2 + nút safe-stop riêng"),
                    hw("actuate"))
    p.edge("c4", prot, esp2, "", pw, exit_=(1, 0.9), entry=(0, 0.5), points=[(370, 653), (370, 875)])

    # Cột D: ngoại vi của J1
    mods = [("d_n", "Bắc", 90), ("d_s", "Nam", 160), ("d_e", "Đông", 240), ("d_w", "Tây", 310)]
    for cid, name, y in mods:
        p.vertex(cid, 1340, y, 320, 50, label(f"Module đèn hướng {name}", "R · Y · G · GND · một mặt của cụm đèn trên trụ",
                                              title_size=12), hw("actuate"))
    sig = edge_style("command", width=1.6)
    p.edge("d1", ns, "d_n", "", sig, exit_=(1, 0.5), entry=(0, 0.5))
    p.edge("d2", ns, "d_s", "", sig, exit_=(1, 0.5), entry=(0, 0.5))
    p.edge("d3", ew, "d_e", "", sig, exit_=(1, 0.5), entry=(0, 0.5))
    p.edge("d4", ew, "d_w", "", sig, exit_=(1, 0.5), entry=(0, 0.5))
    p.vertex("d_stop", 1340, 395, 320, 60,
             label("Nút nhấn tự giữ (safe-stop)", "GPIO 4 ↔ GND: nhấn = LOW = dừng an toàn", title_size=12),
             hw("safety"))
    p.edge("d5", stp, "d_stop", "", edge_style("feedback", end="none", width=1.6) .replace(FLOW["feedback"],
                                                                                          TIER["safety"][1]),
           exit_=(1, 0.5), entry=(0, 0.5))
    la = p.vertex("d_la", 1340, 520, 320, 90,
                  label("Logic analyzer 8 kênh (tùy chọn)", "CH0–CH5 ← GPIO 23/22/21/19/18/5<br>"
                        "CH6 ← GPIO 4 · bằng chứng thời gian độc lập", title_size=12),
                  box_style("shared", dashed=True))
    p.edge("d6", la, esp, "kẹp song song", edge_style("physical", dashed=True), exit_=(0, 0.5),
           entry=(1, 0.704))

    legend(p, 440, 950, [("power", "Nguồn điện", False, False),
                         ("command", "Tín hiệu điều khiển đèn", False, False),
                         ("physical", "Dữ liệu / mạng", False, False)])
    return p


# ---------------------------------------------------------------- H3.3 Kiến trúc phần mềm
def page_software() -> Page:
    p = Page("H3.3 Kiến trúc phần mềm", 1700, 1150)

    pi = p.vertex("pi", 40, 40, 450, 700, "RASPBERRY PI 5 — Raspberry Pi OS (Trixie) · Python 3",
                  container_style("edge_ai"))
    rows = [
        ("s1", "Nguồn video", "Picamera2 qua CSI · toàn khung cảm biến · khóa lấy nét · chống nhấp nháy 50 Hz",
         "video_source.py"),
        ("s2", "Bộ phát hiện xe", "YOLO11n ONNX qua OpenCV DNN ≥ 4.8 · cỡ vào 640 / 480 / 416 / 320",
         "detector.py"),
        ("s3", "Nhận thức theo ROI", "đếm xe trong vùng của từng hướng · mỗi camera một nút (VISION_NODE_IDS)",
         "perception_engine.py · roi_config.py"),
        ("s4", "Cửa sổ telemetry", "trung vị mỗi kỳ 1 s · độ tin cậy = tỉ lệ frame xử lý được",
         "telemetry_window.py"),
        ("s5", "Theo dõi pha đèn", "lấy pha đang chạy từ health/{node} của ESP32", "phase_tracker.py"),
        ("s6", "Đóng gói và gửi", "kiểm JSON Schema → telemetry · health retained + LWT · đo FPS, độ trễ",
         "main.py · runtime_stats.py"),
    ]
    for i, (cid, t, s, m) in enumerate(rows):
        p.vertex(cid, 25, 55 + i * 92, 400, 74, label(t, s, m), box_style("edge_ai"), pi)
    p.vertex("s7", 25, 615, 400, 66,
             label("Dịch vụ hệ thống", "systemd chạy vision khi khởi động · chrony phát giờ NTP cho LAN",
                   "infra/rpi/setup_pi.sh · preflight.sh"), box_style("shared", dashed=True), pi)
    o = edge_style("observe", width=1.5)
    for a, b in (("s1", "s2"), ("s2", "s3"), ("s3", "s4")):
        p.edge(f"pe_{a}", a, b, "", o)
    p.edge("pe_s4", "s4", "s6", "", o, exit_=(1, 0.5), entry=(1, 0.5), points=[(480, 408), (480, 592)])
    p.edge("pe_s5", "s5", "s6", "", edge_style("feedback", width=1.5))

    lap = p.vertex("lap", 630, 40, 490, 700, "MÁY CHỦ ĐIỀU PHỐI — Docker Compose (profile hardware)",
                   container_style("control"))
    mq = p.vertex("c1", 25, 55, 440, 80, label("mqtt", "Eclipse Mosquitto 2.0 · cổng 1883",
                                               "image: eclipse-mosquitto:2.0"), hw("network"), lap)
    gc = p.vertex("c2", 25, 195, 360, 120,
                  label("graph-control", "đọc telemetry/+ → chọn pha từng nút → gửi command<br>"
                        "fixed_time · actuated · max_queue ·<br><b>max_pressure · edgeflow</b>",
                        "services/graph-control/controller.py"), box_style("control"), lap)
    api = p.vertex("c3", 25, 345, 440, 96,
                   label("api", "FastAPI :8000 · nhận trạng thái trực tiếp qua MQTT · topology, thí nghiệm,<br>"
                         "đổi bộ điều khiển, ghi đè pha thủ công · đẩy cập nhật qua WebSocket",
                         "services/api/main.py"), box_style("control"), lap)
    dash = p.vertex("c4", 25, 475, 440, 86,
                    label("dashboard", "React 18 + Recharts :3000 · nhận dữ liệu từ api qua WebSocket,<br>"
                          "REST khi WebSocket mất kết nối",
                          "services/dashboard/"), box_style("control"), lap)
    p.vertex("c5", 25, 595, 440, 86,
             label("simulator SUMO · actuator ảo", "chỉ chạy ở chế độ mô phỏng, cùng hợp đồng dữ liệu<br>"
                   "tắt khi điều khiển đèn thật"), box_style("shared", dashed=True), lap)
    p.edge("ce1", mq, gc, "telemetry/+", edge_style("observe"), exit_=(0.3, 1), entry=(0.367, 0),
           label_offset=(-46, 0))
    p.edge("ce2", gc, mq, "command", edge_style("command"), exit_=(0.6, 0), entry=(0.491, 1), label_offset=(38, 0))
    p.edge("ce3", api, dash, "WebSocket · REST", edge_style("physical", both=True, width=1.4), exit_=(0.5, 1),
           entry=(0.5, 0))
    p.edge("ce4", mq, api, "edgeflow/v1/#", edge_style("observe"), exit_=(0.92, 1), entry=(0.92, 0))

    esp = p.vertex("esp", 1200, 40, 460, 700, "ESP32 — firmware C++ (Arduino-ESP32 · PlatformIO)",
                   container_style("actuate"))
    frows = [
        ("f1", "Kết nối", "Wi-Fi STA · MQTT (PubSubClient) tự nối lại sau 2 s · LWT OFFLINE · SNTP", "actuate"),
        ("f2", "Kiểm tra lệnh", "đúng nút · pha tồn tại · còn hạn · không safe-stop · đủ min green", "actuate"),
        ("f3", "Máy trạng thái đổi pha", "GREEN → YELLOW 3 s → ALL_RED 2 s → GREEN<br>APPLIED chỉ gửi khi đèn đã đổi",
         "actuate"),
        ("f4", "Giám sát an toàn", "mất lệnh &gt; 5 s → fallback 15 s/pha · max green 60 s<br>"
                                   "watchdog phần cứng 10 s", "actuate"),
        ("f5", "Safe-stop", "GPIO 4, chống dội 50 ms → vàng nhấp nháy, từ chối lệnh", "safety"),
        ("f6", "Xuất đèn và bằng chứng", "6 chân GPIO → module đèn · dòng TRACE qua serial → verify_trace.py",
         "actuate"),
    ]
    for i, (cid, t, s, tier) in enumerate(frows):
        p.vertex(cid, 25, 55 + i * 104, 400, 84, label(t, s),
                 box_style(tier, white=(tier != "safety")), esp)
    c = edge_style("command", width=1.5)
    p.edge("fe1", "f1", "f2", "", c)
    p.edge("fe2", "f2", "f3", "", c)
    p.edge("fe3", "f4", "f3", "ép đổi pha", edge_style("command", width=1.5), label_offset=(44, 0))
    p.edge("fe4", "f5", "f6", "ghi đè đầu ra", edge_style("command", width=1.5).replace(
        FLOW["command"], TIER["safety"][1]), label_offset=(50, 0))
    p.edge("fe5", "f3", "f6", "", c, exit_=(1, 0.5), entry=(1, 0.5), points=[(1645, 345), (1645, 657)])

    # Liên kết MQTT giữa các máy
    p.edge("x1", "s6", mq, "telemetry", edge_style("observe"), exit_=(1, 0.5), entry=(0, 0.25),
           points=[(595, 592), (595, 115)], label_pos=-0.1)
    p.edge("x2", mq, "s5", "health", edge_style("feedback", extra=JUMP), exit_=(0, 0.75), entry=(1, 0.5),
           points=[(530, 155), (530, 500)], label_pos=-0.2)
    p.edge("x3", mq, "f1", "command", edge_style("command"), exit_=(1, 0.3), entry=(0, 0.3),
           label_offset=(0, -11))
    p.edge("x4", "f1", mq, "ack, health", edge_style("feedback"), exit_=(0, 0.8), entry=(1, 0.75),
           label_offset=(0, 11))

    con = p.vertex("contracts", 40, 790, 1620, 80,
                   label("contracts/ — hợp đồng dữ liệu dùng chung (nguồn chuẩn duy nhất)",
                         "JSON Schema: telemetry · control_command · control_ack · topology (nút, hướng, pha của khu vực; "
                         "sa bàn: J1, J2) · contracts_sdk.py<br>Đổi khu vực điều khiển = đổi file topology "
                         "(EDGEFLOW_TOPOLOGY), không sửa mã dịch vụ", title_size=14), hw("shared"))
    sh = edge_style("planned", dashed=True, width=1.3)
    p.edge("k1", pi, con, "kiểm schema", sh, exit_=(0.5, 1), entry=(0.1389, 0))
    p.edge("k2", lap, con, "kiểm schema", sh, exit_=(0.5, 1), entry=(0.5154, 0))
    p.edge("k3", esp, con, "cùng định dạng JSON", sh, exit_=(0.5, 1), entry=(0.858, 0))

    rows_t = [
        ["Topic MQTT", "Bên gửi", "Bên nhận", "Tần suất và nội dung"],
        ["edgeflow/v1/telemetry/{node}", "vision (Pi)", "graph-control, api",
         "1 lần/giây/nút: hàng đợi, lưu lượng, độ tin cậy từng hướng, pha hiện tại"],
        ["edgeflow/v1/control/{node}/command", "graph-control (api: ghi đè thủ công)", "ESP32 của nút đó",
         "mỗi chu kỳ quyết định: pha đích, min/max green"],
        ["edgeflow/v1/control/{node}/ack", "ESP32", "api: lưu và hiển thị (*)",
         "ACCEPTED → APPLIED, hoặc REJECTED / EXPIRED / FAILED"],
        ["edgeflow/v1/health/{node}", "ESP32", "vision (phase_tracker)",
         "mỗi 5 s và mỗi lần vào GREEN; LWT OFFLINE khi mất kết nối"],
        ["edgeflow/v1/health/vision", "vision (Pi)", "giám sát",
         "retained: FPS, độ trễ xử lý, trạng thái phần cứng; LWT OFFLINE"],
    ]
    p.table("tbl", 40, 900, [340, 270, 250, 760], rows_t, row_h=32, size=12, mono_cols=(0,))
    p.text("tbl_note", 40, 1098, 1620, 26,
           "(*) graph-control chưa đăng ký topic ack, nên ACK chưa tham gia vào quyết định điều khiển. "
           "Mỗi ESP32 chỉ nhận lệnh có node_id của chính nó.", size=11, color="#555555")
    return p


# ---------------------------------------------------------------- H3.4 Máy trạng thái an toàn
def page_fsm() -> Page:
    p = Page("H3.4 Máy trạng thái an toàn", 1600, 960)
    grp = p.vertex("grp", 60, 60, 1020, 620,
                   "CHU TRÌNH ĐỔI PHA AN TOÀN — thời gian do thiết bị quyết định, bộ điều khiển không rút ngắn được",
                   container_style("actuate", size=13, dashed=True))

    def state(cid: str, x: int, y: int, w: int, h: int, val: str, fill: str, stroke: str) -> str:
        sty = style(rounded=1, arcSize=24, whiteSpace="wrap", html=1, fillColor=fill, strokeColor=stroke,
                    strokeWidth=2.2, fontFamily="Helvetica", fontSize=12, fontColor="#1F1F1F")
        return p.vertex(cid, x, y, w, h, val, sty)

    g = state("st_green", 300, 330, 250, 110,
              label("GREEN — pha P", "min green ≥ 5 s · max green ≤ 60 s<br>hướng của P xanh, hướng còn lại đỏ",
                    title_size=15), "#DDF2E3", "#2F7D4F")
    y = state("st_yellow", 760, 130, 250, 100, label("YELLOW", "3 s · hướng đang xanh chuyển vàng", title_size=15),
              "#FFF2CF", "#B7791F")
    r = state("st_allred", 760, 520, 250, 100, label("ALL_RED", "2 s · mọi hướng đỏ", title_size=15),
              "#FCE1E1", "#C0392B")
    s = state("st_safe", 1260, 330, 300, 120,
              label("SAFE_STOP", "mọi đèn vàng nhấp nháy (0,5 s sáng / 0,5 s tắt)<br>mọi lệnh → REJECTED",
                    title_size=15), "#C0392B", "#7F1D1D")
    # chữ trắng cho SAFE_STOP
    p.cells[-1] = p.cells[-1].replace("fontColor=#1F1F1F", "fontColor=#FFFFFF").replace(
        "color:#4A4A4A", "color:#FFE9E9")

    t = edge_style("physical", width=2, size=12, extra={"fontColor": "#1F1F1F"})
    p.edge("t1", g, y, "<b>Đổi pha khi:</b><br>• có lệnh hợp lệ, đã đủ min green → ACK ACCEPTED<br>"
                       "• hoặc đạt max green 60 s<br>• hoặc fallback: hết 15 s xanh", t,
           exit_=(0.5, 0), entry=(0, 0.5), points=[(425, 180)], label_pos=0.15, label_offset=(0, -40))
    p.edge("t2", y, r, "sau 3 s", t, exit_=(0.5, 1), entry=(0.5, 0), label_offset=(30, 0))
    p.edge("t3", r, g, "sau 2 s → GREEN pha đích<br>ACK APPLIED + gửi health", t, exit_=(0, 0.5),
           entry=(0.5, 1), points=[(425, 570)], label_pos=-0.2, label_offset=(0, 26))
    p.edge("t4", g, g, "lệnh cùng pha<br>→ APPLIED, gia hạn xanh", t, exit_=(0, 0.3), entry=(0, 0.75),
           points=[(250, 363), (250, 412.5)], label_offset=(-80, 0))

    p.vertex("fb_note", 585, 285, 270, 170,
             label("Chế độ FALLBACK", "không nhận lệnh &gt; 5 s → tự đổi pha sau mỗi 15 s xanh, vẫn đi qua "
                   "YELLOW → ALL_RED, không gửi ACK.<br>Có lệnh mới → thoát fallback.", title_size=13),
             box_style("shared", dashed=True, align="left"))

    start = p.vertex("start", 873, 735, 24, 24, "", style(shape="ellipse", perimeter="ellipsePerimeter",
                                                          fillColor="#1F1F1F", strokeColor="#1F1F1F"))
    p.edge("t0", start, r, "cấp nguồn hoặc reset<br>(watchdog phần cứng 10 s)", t, exit_=(0.5, 0),
           entry=(0.5, 1), label_pos=-0.5, label_offset=(110, 0))

    sf = edge_style("physical", width=2.2, size=12, extra={"strokeColor": "#C0392B", "fontColor": "#7F1D1D"})
    p.edge("t5", grp, s, "nhấn safe-stop<br>(GPIO 4 = LOW ≥ 50 ms)<br>lệnh đang chờ → FAILED", sf,
           exit_=(1, 0.532), entry=(0, 0.5), label_offset=(0, -46))
    p.edge("t6", s, r, "nhả nút → ALL_RED 2 s<br>rồi xanh lại pha cũ", sf, exit_=(0.5, 1), entry=(1, 0.8),
           points=[(1410, 600)], label_pos=-0.4, label_offset=(70, 0))

    p.vertex("rej", 60, 740, 700, 150,
             label("Lệnh bị từ chối thì đèn giữ nguyên trạng thái",
                   "• pha không thuộc nút, JSON sai → REJECTED<br>"
                   "• đang chuyển sang pha khác → REJECTED<br>• chưa đủ min green → REJECTED<br>"
                   "• quá hạn (khi lệnh có expires_at_ms và đồng hồ đã đồng bộ) → EXPIRED<br>"
                   "• lệnh gửi cho nút khác → bỏ qua", title_size=13),
             box_style("shared", align="left"))
    p.table("out", 1000, 740, [190, 175, 175], [
        ["Trạng thái", "Bắc – Nam", "Đông – Tây"],
        ["GREEN (P = NS)", "Xanh", "Đỏ"],
        ["YELLOW (từ NS)", "Vàng", "Đỏ"],
        ["ALL_RED", "Đỏ", "Đỏ"],
        ["GREEN (P = EW)", "Đỏ", "Xanh"],
        ["SAFE_STOP", "Vàng nhấp nháy", "Vàng nhấp nháy"],
    ], row_h=28, size=12)
    return p


def main() -> int:
    pages = [page_block(), page_hardware(), page_software(), page_fsm()]
    write_drawio(str(OUT), pages)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
