## Mô Tả Thay Đổi (Description)
<!-- Tóm tắt ngắn gọn tính năng hoặc lỗi được xử lý trong PR này -->

## Loại Thay Đổi (Type of Change)
- [ ] 🚀 Feature (Tính năng mới)
- [ ] 🐛 Bug fix (Sửa lỗi)
- [ ] 🧹 Refactor (Tối ưu hóa mã nguồn)
- [ ] 📝 Documentation (Cập nhật tài liệu)
- [ ] ⚙️ CI/CD / Infrastructure (Cấu hình hạ tầng/tự động hóa)

## Checklist Kiểm Tra Tuân Thủ Architecture (AGENTS.md)
- [ ] Mã nguồn không vi phạm ranh giới microservice (Microservice Isolation).
- [ ] Tin nhắn và Topology ID sử dụng đúng định dạng từ `contracts/` (Schema Authority).
- [ ] Đã chạy `make contracts` và tất cả contract tests đều PASS.
- [ ] Đã chạy `make test` (hoặc `python -m pytest tests/unit`) và 100% tests PASS.
- [ ] Đã bổ sung/cập nhật unit tests cho tính năng mới (nếu có).

## Hướng Dẫn Kiểm Thử (How to Test)
<!-- Liệt kê các bước hoặc lệnh để reviewer kiểm thử thay đổi này -->
1. `python -m pytest tests/unit`
2. `python -m pytest tests/integration`
