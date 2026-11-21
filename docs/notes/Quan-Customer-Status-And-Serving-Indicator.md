# Quán · Thanh trạng thái khách và nhãn bàn khi mang món

Ngày 2026-11-21 · nhánh `tsunami` · chỉ sửa giao diện `chonoi/web/index.html`. Không đổi simulation, Test Contract hay headless.

## 1. Vấn đề ban đầu

- Bếp B1/B2 chỉ hiện tên bếp. Người chơi không biết món đang nấu thuộc bàn nào.
- Cầm món chín xong phải nhìn sang sidebar để tìm bàn.
- Kho nguyên liệu đứng trên danh sách đơn. Độ tươi đổi mỗi tick làm khối kho dài ra và đẩy đơn xuống.
- Trên cảnh không thấy khách nào đang chờ, đang ăn hay sắp bỏ đi.

## 2. Dữ liệu trạng thái khách (đã kiểm trong source)

Snapshot Quán (`QuanSim.snapshot`, `chonoi/sim/quan.py`) có `customers[]` với các trường:

| Trường | Ý nghĩa |
|---|---|
| `id` | ID đơn, cũng là `order_id` của món (`KitchenServingMixin._dish_for`) |
| `table_id` | Bàn của khách |
| `state` | `waiting` hoặc `eating` |
| `order_status` | `reserved`, `assigned`, `unfulfillable`, `served` |
| `patience_ticks_left` | Kiên nhẫn còn lại, giảm khi `waiting` |
| `eat_ticks_left` | Thời gian ăn còn lại, giảm khi `eating` |

Mức tối đa không có trong từng khách, nên lấy từ `meta` (tuning `quan`):

- Kiên nhẫn tối đa = `meta.patience_s × tick_hz`, khớp `patience_max_ticks` trong `kitchen.py`. Nếu snapshot có `patience_max_ticks` thì dùng giá trị đó.
- Thời gian ăn tối đa = `meta.eat_s × tick_hz`, khớp `_ticks(self.t["eat_s"])` khi phục vụ.

Không bổ sung trường mới vào backend.

## 3. Mapping màu

| Màu | Điều kiện | Chữ |
|---|---|---|
| Vàng | `state == "eating"` | Đang ăn |
| Đỏ | `state == "waiting"` và kiên nhẫn còn ≤ 20% | ⚠ Sắp bỏ đi |
| Xanh lá | `state == "waiting"` và kiên nhẫn còn > 20% | Đang chờ |
| (không vẽ) | Khách đã rời, bàn trống hoặc thiếu timer | — |

- Ngưỡng là hằng số UI `CUSTOMER_BAR_DANGER_RATIO = 0.2`. Chọn quy tắc 20% vì phù hợp mọi độ dài kiên nhẫn.
- Khách đang ăn luôn vàng. `patience_ticks_left` cũ của họ không bao giờ được dùng.
- Trạng thái đỏ nhấp nháy chậm, chu kỳ khoảng 1,2 s. Không nhấp nháy khi `prefers-reduced-motion` bật hoặc khi đang tạm dừng.

## 4. Độ dài thanh

`ratio = timer_còn_lại / timer_tối_đa`, kẹp trong [0, 1].

- Chờ: `patience_ticks_left / (patience_s × tick_hz)`.
- Ăn: `eat_ticks_left / (eat_s × tick_hz)`.

Thanh rộng `clamp(size × 0.72, 40, 55)` px, cao 6 px, nền tối, bo góc. Thanh được đặt ngay trên đầu sprite khách. Nó dùng cùng tọa độ và điểm neo với sprite: đáy tại `y + 4`, sprite cao `size × 0.74`. Vì vậy thanh theo đúng tỷ lệ Canvas.

Giá trị chỉ đổi khi có snapshot mới, nên thanh luôn đồng bộ với simulation, kể cả khi tạm dừng.

## 5. Xác định bàn từ món trên tay

Liên kết: `hand.order_id → customers[].id → table_id`, qua hàm `tableForOrder(orderId)`.

- Không suy từ số bếp, bàn gần nhất hay tên món. Hai bàn gọi cùng một món vẫn được phân biệt bằng ID đơn.
- Nhãn `🍽 MANG TỚI T3` vẽ trên đầu Bà Út, phía trên tên nhân vật. Nó dùng cùng tọa độ đã nội suy với sprite đi bộ. Khi vừa nhấc món, nhãn phóng to trong 180 ms rồi đứng yên.
- `hand` về `null` sau khi phục vụ, nên nhãn biến mất. Cầm món khác thì nhãn đổi theo `order_id` mới.
- Không tìm thấy đơn thì hiện `Chưa rõ bàn` (nền đỏ nâu) và ghi `console.warn` một lần cho mỗi `order_id`.
- Bếp: dưới nhãn B1/B2 có `T3 · 5s` khi đang nấu và `T3 · Món chín` khi xong. Dữ liệu lấy từ `stove.dish.order_id`.
- Sidebar: dòng bếp thêm `Bàn T3`, dòng cầm món thêm `→ Bàn T3`.

## 6. Sidebar

- `.tray` là flex column. `#orders` (đơn, bếp, tay) lên đầu, `#stock` xuống cuối.
- Kho cao tối đa 210 px, cuộn riêng (`overscroll-behavior: contain`), tiêu đề "Kho nguyên liệu" dính trên đầu vùng cuộn.
- `setHTML` giữ `scrollTop` khi thay nội dung. Vì vậy vị trí cuộn kho không nhảy về đầu khi độ tươi đổi.
- Số liệu đơn/bếp dùng `tabular-nums` để chữ số không làm dòng xê dịch.
- Không bỏ dữ liệu nào khỏi HUD.

## 7. Các file đã sửa

- `chonoi/web/index.html`: hàm `customerStatus`, `drawCustomerBar`, `tableForOrder`, `drawServingBadge`; nhãn bàn ở bếp; sidebar (CSS và `setHTML`).
- `docs/notes/Quan-Customer-Status-And-Serving-Indicator.md`: tài liệu này.

## 8. Kết quả kiểm thử

Kiểm trên trình duyệt (khung app, 1280×720) với `chonoi.live --mode quan --extensions ""` và scenario cố định:

- C1@T1 và C3@T3 cùng gọi gỏi bông súng.
- B1 đã nấu xong món của C3, B2 đang nấu món của C1.
- C2@T2 đang ăn.
- C4@T4 còn khoảng 21% kiên nhẫn.

| Test | Kết quả |
|---|---|
| A · khách chờ | T1 và T3 xanh "Đang chờ", thanh ngắn dần. T4 sang đỏ "⚠ Sắp bỏ đi" khi xuống ≤ 20%, sau đó T1 và T3 cũng đỏ dần. Khách hết kiên nhẫn rời thì thanh mất. |
| B · khách ăn | C2@T2 ăn xong, thanh tự mất. Phục vụ C3 thì T3 vàng "Đang ăn" với ratio 0,31, dù `patience_ticks_left` vẫn còn 248. |
| C · nhãn bàn | Lấy B1 thì `hand.order_id = C3` và nhãn `MANG TỚI T3`. Phục vụ T3 thì `hand = null`, nhãn mất. Lấy B2 (cùng món) thì `order_id = C1` và nhãn `MANG TỚI T1`. Bếp hiện `T3 · Món chín` và `T1 · 5s`. |
| D · nhiều khách | Bốn bàn hiện bốn trạng thái độc lập (xanh, vàng, đỏ, không thanh) trong cùng khung hình. |
| E · UI | Cuộn kho tới 60 px, sau 2,5 s cập nhật độ tươi vẫn ở 60 px. Vị trí khối đơn không đổi. Console không có lỗi JS; các lỗi `ERR_CONNECTION_REFUSED` là do tôi tắt server thử. |
| F · hồi quy | `python -m unittest discover -s tests`: 281 test. Chỉ còn lỗi `test_live.test_serves_phase_two_art` do timeout tải ảnh WebP, lỗi chập chờn đã có từ trước khi sửa. |

## 9. Hạn chế còn lại

- Khi Bà Út đứng sát bàn, sprite và nhãn tên của bà có thể đè lên thanh của khách bàn đó. Thứ tự vẽ giữ nhân viên trên khách để không che nhân viên.
- Trong phiên thử, Quán chỉ có trạng thái pause ở bản web nhiều ngày. Phần pause mới được suy ra từ logic (thanh chỉ đổi theo snapshot), chưa chạy riêng trên trình duyệt.
- Khách hiện không có hoạt ảnh đi từ cửa vào bàn, mà xuất hiện tại bàn. Nếu sau này thêm hoạt ảnh, cần gọi `drawCustomerBar` với vị trí đang nội suy của khách.
- Chưa có test tự động cho phần vẽ Canvas. Kiểm chứng phần này dựa trên trình duyệt.
