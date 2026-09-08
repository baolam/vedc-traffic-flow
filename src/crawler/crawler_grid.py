import json
import time
import os
from playwright.sync_api import sync_playwright

def crawl_cameras_grid_v3():
    print("🚀 Bắt đầu quá trình quét Camera theo LƯỚI SIÊU NHỎ (Grid 8x8)...")
    
    output_dir = "data/grid_data"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Đang tải Cổng TTGT TP.HCM...")
        try:
            page.goto("https://giaothong.hochiminhcity.gov.vn/Map.aspx", timeout=60000)
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Lỗi khi tải trang web: {e}")
            browser.close()
            return

        # TP.HCM Bounding Box
        lng_min, lng_max = 106.3, 107.0
        lat_min, lat_max = 10.3, 11.2
        steps = 8 # Chia lưới thành 8x8 = 64 ô nhỏ hơn rất nhiều

        lng_step = (lng_max - lng_min) / steps
        lat_step = (lat_max - lat_min) / steps

        total_cells = steps * steps
        current_cell = 0
        all_cameras = {}

        print(f"Bản đồ được chia thành {total_cells} ô siêu nhỏ để quét triệt để.")
        print("Đã bật tính năng: Trích xuất Tên đường và Quận/Huyện.")
        print("-" * 50)

        for i in range(steps):
            for j in range(steps):
                current_cell += 1
                left = lng_min + i * lng_step
                right = left + lng_step
                bottom = lat_min + j * lat_step
                top = bottom + lat_step

                print(f"\n⏳ [Ô {current_cell}/{total_cells}] Tọa độ: Lng({left:.2f}->{right:.2f}), Lat({bottom:.2f}->{top:.2f})")
                
                # JS Code trích xuất toàn bộ thông tin (bao gồm Tên đường, Quận) ngay trên trình duyệt
                js_code = f"""
                () => {{
                    return new Promise((resolve) => {{
                        let isResolved = false;
                        
                        let fallbackTimeout = setTimeout(() => {{
                            if (!isResolved) {{
                                isResolved = true;
                                resolve([]);
                            }}
                        }}, 6000); // 6 giây timeout cho ô nhỏ

                        if (typeof VDMS !== 'undefined' && VDMS.Web.Library.AJAX.LayerAjax) {{
                            VDMS.Web.Library.AJAX.LayerAjax.GetObjectsByRect(
                                "CAMERA", {left}, {bottom}, {right}, {top}, [],
                                function(res) {{
                                    if (!isResolved) {{
                                        isResolved = true;
                                        clearTimeout(fallbackTimeout);
                                        
                                        if (res && res.value) {{
                                            // Chế biến dữ liệu ngay trên trình duyệt
                                            let parsed = res.value.map(item => {{
                                                let lat = 0, lng = 0;
                                                try {{
                                                    let shapeStr = JSON.stringify(item[4]);
                                                    let match = shapeStr.match(/POINT\\((10\\d\\.\\d+)\\s+(10\\.\\d+)\\)/);
                                                    if (match) {{
                                                        lng = parseFloat(match[1]);
                                                        lat = parseFloat(match[2]);
                                                    }}
                                                }} catch(e) {{}}
                                                
                                                return {{
                                                    id: item[2],
                                                    name: item[0],
                                                    district: item[7] || "Không rõ",
                                                    street: item[13] || "Không rõ",
                                                    lat: lat,
                                                    lng: lng,
                                                    status: "Online"
                                                }};
                                            }}).filter(c => c.lat !== 0 && c.lng !== 0);
                                            resolve(parsed);
                                        }} else {{
                                            resolve([]);
                                        }}
                                    }}
                                }}
                            );
                        }} else {{ 
                            if (!isResolved) {{
                                isResolved = true;
                                clearTimeout(fallbackTimeout);
                                resolve([]); 
                            }}
                        }}
                    }});
                }}
                """
                
                try:
                    start_time = time.time()
                    cell_cameras = page.evaluate(js_code)
                    elapsed = time.time() - start_time
                    
                    if cell_cameras:
                        for cam in cell_cameras:
                            cam_id = cam['id']
                            if cam_id not in all_cameras:
                                all_cameras[cam_id] = cam
                                # In thông tin có kèm tên đường
                                street_display = cam['street'][:30] + "..." if len(cam['street']) > 30 else cam['street']
                                print(f"   [+] {cam_id} | {cam['name']} | Đ/c: {street_display}")

                    # Lưu danh sách camera của ô hiện tại ra file riêng
                    cell_file = os.path.join(output_dir, f"cell_{current_cell}.json")
                    with open(cell_file, "w", encoding="utf-8") as f:
                        json.dump(cell_cameras, f, ensure_ascii=False, indent=2)
                        
                    print(f"   -> Ô {current_cell} quét mất {elapsed:.1f}s. Lưu {len(cell_cameras)} camera vào {cell_file}.")

                except Exception as e:
                    print(f"   ❌ Lỗi khi quét ô này: {e}")
                
                time.sleep(0.5)

        browser.close()

    print("\n" + "=" * 50)
    print("🔄 Bắt đầu gộp các file json con...")
    final_unique = {}
    
    for filename in os.listdir(output_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for cam in data:
                        final_unique[cam['id']] = cam
                except Exception as e:
                    pass

    final_output = "data/raw/cameras_hcm_full.json"
    with open(final_output, "w", encoding="utf-8") as f:
        json.dump(list(final_unique.values()), f, ensure_ascii=False, indent=2)
        
    print(f"🎉 Hoàn tất toàn bộ! Đã gộp tổng cộng {len(final_unique)} camera (Kèm TÊN ĐƯỜNG) vào file '{final_output}'.")

if __name__ == "__main__":
    crawl_cameras_grid_v3()
