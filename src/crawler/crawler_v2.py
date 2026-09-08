import json
import time
import re
import os
from playwright.sync_api import sync_playwright

def crawl_cameras_v2():
    print("🚀 Bắt đầu Crawler V2: Chế độ 'Đánh chặn' lưới Mạng (Network Intercept)...")
    print("Giải thích: Chế độ bắn API trực tiếp đã bị Server chặn. Ta sẽ mô phỏng người dùng kéo bản đồ và bắt gói tin thô trên mạng!")
    
    output_dir = "data/intercept_data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    all_cameras = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        # Hàm Đánh chặn luồng mạng
        def handle_response(response):
            if "ajaxpro" in response.url.lower() and response.status == 200:
                try:
                    raw_text = response.text()
                    
                    # Regex bóc tách Dữ liệu thô. 
                    # Tìm Mảng: ["Tên", ..., "ID", ... POINT(Lng Lat) ... ]] ), "Snapshot", "Group", "Quận", "True", null, "UP", "False", Angle, "Tên Đường"
                    pattern = r'\["([^"]+)",(?:null|"[^"]*"),"([a-f0-9]{24})",.*?POINT\((10\d\.\d+)\s+(10\.\d+)\).*?\]\]\)(.*?)(?:\]\s*,|\]\])'
                    matches = re.finditer(pattern, raw_text)
                    
                    new_found = 0
                    for match in matches:
                        name = match.group(1)
                        cam_id = match.group(2)
                        lng = float(match.group(3))
                        lat = float(match.group(4))
                        rest_of_string = match.group(5)
                        
                        # Trích xuất các trường còn lại bằng regex tìm chuỗi hoặc số
                        fields = re.findall(r'"([^"]*)"|\b\d+\b|null|True|False', rest_of_string)
                        # fields thường có dạng: [Snapshot, Group, District, True, null, UP, False, Angle, Street, ...]
                        
                        district = "Không rõ"
                        street = "Không rõ"
                        
                        # Lọc ra các chuỗi thực sự (bỏ qua null, True, False, UP, số)
                        valid_strings = [f for f in fields if f and f not in ('null', 'True', 'False', 'UP') and not f.isdigit()]
                        
                        if len(valid_strings) >= 3:
                            district = valid_strings[2] # Thường là chuỗi thứ 3 (sau url và group)
                        if len(valid_strings) >= 4:
                            street = valid_strings[3] # Thường là chuỗi thứ 4
                            
                        if cam_id not in all_cameras:
                            all_cameras[cam_id] = {
                                "id": cam_id,
                                "name": name,
                                "district": district,
                                "street": street,
                                "lat": lat,
                                "lng": lng,
                                "status": "Online"
                            }
                            new_found += 1
                            street_display = street[:35] + "..." if len(street) > 35 else street
                            print(f"   [+] Bắt được: {cam_id} | {name} | Đ/c: {street_display}")

                    if new_found > 0:
                        with open("data/raw/cameras_hcm_full.json", "w", encoding="utf-8") as f:
                            json.dump(list(all_cameras.values()), f, ensure_ascii=False, indent=2)
                        
                except Exception as e:
                    pass

        # Cắm chốt chặn mạng
        page.on("response", handle_response)

        print("Đang tải bản đồ TP.HCM...")
        try:
            page.goto("https://giaothong.hochiminhcity.gov.vn/Map.aspx", timeout=60000)
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Lỗi khi tải trang web: {e}")
            browser.close()
            return

        print("\nTự động kích hoạt tải camera...")
        try:
            page.locator("label:has-text('Camera')").first.click()
            page.wait_for_timeout(1000)
            page.locator("label:has-text('Camera')").first.click()
            page.wait_for_timeout(3000)
        except:
            pass

        print("\nBắt đầu tự động KÉO BẢN ĐỒ đi các quận ven để vét sạch dữ liệu...")
        
        # Mô phỏng Kéo chuột 8 lần đi các hướng khác nhau
        directions = [
            (0, -300), (0, 600), # Lên, Xuống
            (-400, 0), (800, 0), # Trái, Phải
            (-300, -300), (600, 600), # Chéo
            (300, -300), (-600, 600)
        ]
        
        for dx, dy in directions:
            # Click giữ chuột ở giữa màn hình rồi kéo
            page.mouse.move(640, 400)
            page.mouse.down()
            page.mouse.move(640 + dx, 400 + dy, steps=10)
            page.mouse.up()
            page.wait_for_timeout(2500) # Đợi bản đồ tải dữ liệu của vùng mới

        print("\n⏳ Đã rảo quanh thành phố xong! Kích hoạt chế độ Thủ công.")
        print("Bây giờ bạn có thể TỰ DÙNG CHUỘT kéo bản đồ đi bất cứ đâu bạn muốn.")
        print("Script vẫn đang mở và Lắng nghe. Cứ kéo tới đâu, bắt dữ liệu tới đó (Đóng sau 20s)...")
        
        page.wait_for_timeout(20000)

        browser.close()
        print(f"\n🎉 Hoàn tất quá trình! Đã lưu tổng cộng {len(all_cameras)} camera (Kèm TÊN ĐƯỜNG) vào cameras_hcm_full.json.")

if __name__ == "__main__":
    crawl_cameras_v2()
