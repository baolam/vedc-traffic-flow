Route generator cho SUMO:
- Mỗi xe có origin/destination thật.
- Shortest path theo free-flow travel time.
- Tối đa 3 tuyến dự phòng cho cùng OD.
- Backup phải là đường hợp lệ, khác đáng kể và không dài quá 160% shortest path.
- 75% xác suất chọn backup nếu có.
- Kiểm tra route liên tục theo from/to của edge.
- Không dùng internal edge (:...).
- vType đứng trước vehicle.

Chạy:
generate_routes.bat

Hoặc một dòng:
python "E:\vedc-traffic-flow\experiments\example\route_generator.py" -n "E:\vedc-traffic-flow\experiments\example\network.net.xml" -o "E:\vedc-traffic-flow\experiments\example\routes.rou.xml" -v 1000 --end 3600 --seed 42 --min-distance 300 --alternatives 3 --max-detour 1.60 --alt-prob 0.75

Lưu ý: backup ở đây là tuyến dự phòng được chọn khi sinh demand, chưa phải reroute động giữa lúc chạy. Reroute động sẽ làm bằng TraCI.
