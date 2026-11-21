# Changelog
## v1.0.0 — ứng viên, chưa công bố

- Phase 1: Gather/sinh tồn/thu thập, khách, bếp, phục vụ và thanh toán.
- Phase 2: ba loài cá/cá sấu, 2 bếp/4 bàn/6 món, Day Loop/Shop, pause.
- Phase 3: breaking change kho đếm thành items[] `{id,kind,fresh}`, reserved theo ID,
  hao tươi/ươn, giá theo cá thể. V1.3 giữ schema v1.2, từ chối kho đếm cũ.
- Phase 4: benchmark Canvas thật, soak 10 ngày, cảnh báo/High Contrast, manifest 1.3,
  tài liệu và đóng gói ứng viên. Chưa gắn tag hoặc công bố GitHub Release.
- Web riêng: map/camera/animation, stack linh, menu unlock/spawn, Auto End,
  chỉ dẫn phục vụ; current/reservations chỉ bật theo cấu hình, giữ preset chuẩn.

## Unreleased

- **Gather độ tươi (P3-01):** nguyên liệu trong giỏ hao 0.5/s từ tick sau khi nhặt; `spoiled` phát đúng một lần khi xuống dưới 30 với payload `{item_id, kind, location}`. `snapshot.hold` và `lost` của `faint`/`monster_hit` là mảng object `{id, kind, fresh}`. `gather_end` giữ nguyên `inventory.items`. Hằng số lấy từ `tuning.inventory`; khóa `initial_fresh` mới (100).
- UI giỏ: hiển thị độ tươi (tooltip ô giỏ) và dòng nhật ký khi nguyên liệu ươn.
- Test: `test_gather_freshness.py` viết lại theo API v1.2; các assert `lost`/`fresh` ở test cũ đổi theo spec (object và hao tươi 1 tick trước khi bến).

## [1.2.0] - Phase 3 (TICKET-03)

- **Breaking change — file kho JSON:** `items` chuyển từ map đếm số lượng như `{"items":{"ca_loc":2}}` sang mảng cá thể như `{"items":[{"id":"I1","kind":"ca_loc","fresh":100.0}]}`. Mỗi nguyên liệu có ID duy nhất và độ tươi riêng; kho rỗng là `{"items":[]}`.
- `--inventory` từ chối file kho định dạng cũ hoặc cá thể sai schema với exit code `2`. Gather ghi `--inventory-out` nguyên tử; Day chuyển nguyên `id`, `kind`, `fresh` sang Quán.
- Quán v1.2 hao tươi từng cá thể. `customers[].reserved` dùng mảng ID như `["I1"]` và `cook_started.data.items` ghi các cá thể thực tế đã dùng. Các fixture kiểm v1.2 dùng mảng trong `quan.stock`. Adapter nội bộ vẫn cho phép fixture Quán đếm của Phase 1/2.

### P3-04 trước tích hợp (lịch sử)
### P3-04 — chuẩn bị tích hợp Test Contract v1.2

- Thêm helper bếp tiêu đúng cá thể đã giữ và chốt giá theo độ tươi trung bình, event `cook_started.items` là object sắp kind/ID. Giá được giữ qua phục vụ/thanh toán.
- Breaking change đích v1.2: `stock`/file `items` từ map đếm sang mảng `{id,kind,fresh}`, `reserved` thành mảng ID; khi bật v1.2 phải từ chối kho đếm với mã 2. Migration thuộc P3-02/P3-03 **chưa tích hợp**; manifest/CLI hiện vẫn v1.1, không âm thầm nhận schema mới.
- Không sửa/xóa test P1/P2; 17 test mới dùng mock ranh giới P3-03 có ghi nhãn. Chi tiết và giới hạn tại `docs/notes/P3-04.md`.
