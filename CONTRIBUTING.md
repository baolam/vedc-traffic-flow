# Contributing Guidelines (Quy Chuẩn Đóng Góp Mã Nguồn)

Để đảm bảo chất lượng hệ thống **EdgeFlow AI**, tất cả các đóng góp mã nguồn (Pull Requests) cần tuân thủ tuyệt đối các quy định dưới đây:

---

## 1. Quy định đặt tên Nhánh (Branch Naming Convention)

- Tính năng mới: `feat/<module>-<short-description>` (ví dụ: `feat/graph-control-rl-controller`)
- Sửa lỗi: `fix/<module>-<short-description>` (ví dụ: `fix/actuator-state-timeout`)
- Refactor / Tối ưu hoá: `refactor/<module>-<short-description>`
- Tài liệu: `docs/<short-description>`

---

## 2. Thông điệp Commit chuẩn (Conventional Commits)

Định dạng commit message:
```text
<type>(<scope>): <short description>
```
Ví dụ:
- `feat(graph-control): add pydantic-settings configuration support`
- `fix(actuator): resolve yellow-to-all-red transition timing issue`
- `docs(readme): update quickstart guide for Docker environment`

---

## 3. Quy chuẩn Kiến trúc & Schema Invariants (AGENTS.md Compliance)

1. **Schema Authority**: Không tự ý sửa đổi Schema gốc tại microservices cá nhân. Tất cả tin nhắn, enum, topology ID phải xuất phát từ `contracts/`.
2. **Microservice Isolation**: Không import trực tiếp mã nguồn giữa các microservices. Mọi giao tiếp diễn ra qua MQTT hoặc REST/WebSocket API.
3. **Controller & Actuator Abstraction**: Mọi controller phải kế thừa từ abstract interface chung. Mọi actuator đều nhận cùng định dạng `ControlCommand`.

---

## 4. Kiểm thử bắt buộc trước khi tạo Pull Request

Trước khi push hoặc tạo PR, phát triển viên cần chạy lệnh kiểm tra toàn bộ hệ thống:

```bash
# Kiểm tra hợp đồng Schema & Unit tests
make check-all

# Hoặc bằng pytest trực tiếp:
python -m pytest tests/unit
python -m pytest tests/integration
```

Tất cả các bài kiểm tra phải PASS 100% trước khi mở Pull Request.
