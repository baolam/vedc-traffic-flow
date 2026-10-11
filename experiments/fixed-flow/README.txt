Bản hoàn chỉnh: 3000 xe = 60% normal, 15% fixed-flow, 15% random-end, 10% irregular.
Fixed-flow tự phát hiện corridor và khóa route. Normal có tối đa 3 backup route.
Random-end cho phép bắt đầu/kết thúc giữa mạng. Irregular random-walk nhưng vẫn theo connection hợp lệ.
routes.rou.xml không chứa vType; vType giữ trong vehicles.rou.xml.
Chạy generate_complete_routes.bat. Sau đó xem fixed_corridors.txt.
