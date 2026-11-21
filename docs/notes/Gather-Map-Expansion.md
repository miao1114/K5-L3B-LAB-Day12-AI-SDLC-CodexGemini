# Gather · Mở rộng bản đồ, camera theo nhân vật, cá bơi tự nhiên

Ngày 2026-11-21 · nhánh `statuswaiting` (chưa commit) · chỉ áp dụng cho bản web 5 ngày (`docs/proof/phase-2/day_fixture.py --real-scenes`).

Headless/Test Contract và `chonoi.live` vẫn dùng sông 100 m như cũ.

## 1. Kích thước thế giới

| | Trước | Sau (bản web) |
|---|---|---|
| Chiều dài sông `bounds.x` | 0–100 m | 0–200 m |
| Độ sâu `bounds.d` | 0–30 m | 0–30 m (giữ nguyên, oxy không đổi) |
| Bến `dock_pos`, điểm xuất phát | [2, 0] | [2, 0] |
| Biên bơi của cá `fish_x` | 4–96 | 4–196 |

Cấu hình nằm ở `chonoi/web/gameplay.json`:

```json
"gather_world": {"length_m": 200, "natural_fish": true}
```

Module `chonoi/interactive_world.py` (`world_tuning`) giãn tọa độ x và chỉ được `InteractiveDaySim._start_day` gọi. Nó nhận `length_m` trong khoảng 1–4 lần chiều dài chuẩn; khóa lạ bị từ chối với mã lỗi 2.

## 2. Giữ nguyên spawn và luật

- **Giữ nguyên:** `fish_initial` (8), `fish_max` (12), `fish_spawn_ticks`, `fish_spawn_clearance`, `regrow_s`, `fish_yield` (cá linh 3, cá kèo 2, cá lóc 1), độ tươi, giỏ và cá linh xếp ×3.
- **Cây:** vẫn 6 điểm, x được giãn theo tỷ lệ (12–90 thành 24–180). Loại cây vẫn theo món đã mở khóa (`resource_tuning` chạy trước).
- **Điểm sinh cá** `fish_spawn_x`: 6 điểm được giãn ra, thêm điểm giữa, thành 11 điểm từ 30 đến 180 m. Số đàn cá vẫn do `fish_initial`/`fish_max` quyết định, không tăng theo kích thước bản đồ.
- **Cá sấu:** cùng số lượng và cùng luật. Chỉ vị trí và waypoint được giãn x (M1 từ 60 sang 120). Cá sấu không được nhân đôi theo nền.
- **Đi được trong thời gian ca:** bơi 4 m/s, đi hết 200 m mất 50 s trên tổng 180 s của buổi sáng. Thử thật: bắt cá ở x ≈ 155 m rồi về bến và cập bến mất khoảng 40 s.

## 3. Nền mở rộng

Ảnh `art/gather.webp` (1672×941) không lặp liền được: bên trái có bến, bên phải có cây.

- Giữ nguyên ảnh gốc, cắt tại `ART_CUT = 0.665`, ngay trước mặt trời.
- Chèn `k` cặp dải nước mở `[ART_CUT − dải, ART_CUT]`, xen kẽ dải **lật ngang** và dải **thường**:
  - dải lật bắt đầu bằng đúng cột `ART_CUT`, khớp với mép phải của ảnh gốc đã cắt;
  - dải thường kết thúc bằng cột `ART_CUT`, khớp với phần đuôi `[ART_CUT, 1]` của ảnh gốc.
  - Vì vậy mọi mối nối khớp từng pixel.
- Độ rộng dải được tính sao cho tổng chiều dài nền bằng đúng chiều dài thế giới (200 m: 1 cặp, mỗi dải 0,33 ảnh).
- **Không kéo giãn ngang:** mỗi đoạn vẽ đúng tỷ lệ của ảnh. Chỉ vẽ đoạn nằm trong khung camera, mỗi đoạn rộng thêm 1 px để không hở mối nối.
- Ở chế độ 100 m, nền vẫn là ảnh CSS cũ và camera đứng yên tại 0.

## 4. Camera

- Tỷ lệ cố định theo ảnh gốc: `art_span_m` (100 m) chiếm đoạn `GATHER_ART.left..right` (0,30–0,96 chiều rộng Canvas).
- Phép chiếu world → camera → screen: `x_screen = w·(0.30 + scale·(x − x0) − cameraX)`. Trục dọc giữ nguyên.
- Mọi vật thể trên bản đồ dùng chung hàm `at()` này: Bà Út, cá, cá sấu, cây, vùng lũ, vòng tầm bắt, hiệu ứng bắn nước, cá nền, bọt nước, nhãn.
- **Đích của camera:** Bà Út ở giữa khung (đã nội suy vị trí), kẹp trong `[0, tổng_nền − 1]`. Camera đuổi theo mượt với hằng số thời gian 160 ms; đổi màn hoặc đổi ngày thì camera nhảy thẳng tới đích; khi bật giảm chuyển động thì không làm mượt.
- **Vẽ tiết kiệm:** vật thể ngoài khung (cách hơn 1,5 lần kích thước sprite) không được vẽ, kể cả nhãn.
- HUD (máu, oxy, thời gian, nhiệm vụ) là DOM nằm ngoài Canvas nên không trôi theo camera.

## 5. Chỉ hướng về bến

- **Bến trong khung:** nhãn "Bến · 58 m" phía trên bến, khi Bà Út cách bến xa hơn `dock_radius`.
- **Bến ngoài khung:** một nhãn bo tròn ở mép trái (hoặc phải) ngang mặt nước, ví dụ "◀ Bến 108 m".
- Khoảng cách tính từ vị trí thật trong simulation.

## 6. Cá gameplay bơi tự nhiên (`natural_fish`)

Code nằm ở `InteractiveGather._move_fish` trong `chonoi/interactive.py`. Chỉ bản web dùng; `GatherSim` chuẩn giữ nguyên thuật toán cũ (đổi hướng ngẫu nhiên 0–360° mỗi 120 tick).

- Mỗi đàn cá có một **hướng muốn tới**, ưu tiên bơi ngang (lệch tối đa ±28°). Hướng thật quay dần về đó, tối đa 1,5° mỗi tick, nên cá không giật.
- Thời điểm chọn hướng mới lệch nhau giữa các đàn (ngẫu nhiên 120–360 tick); 30% khả năng quay đầu ngược lại.
- Chạm mép sông hoặc mép độ sâu thì dội lại, đổi cả hướng thật lẫn hướng muốn tới, nên cá không kẹt mép.
- Vẫn dùng stream `fish_swim`, nên kết quả tất định theo seed. Tốc độ vẫn là `fish_speed`.
- **Hitbox:** vị trí vẽ chính là vị trí simulation (nội suy giữa hai snapshot), và vòng tầm bắt dùng cùng `catch_radius`.

## 7. Cá nền và hiệu ứng (chỉ là hình ảnh)

Các thứ sau đều được tính ở client theo thời gian và hàm băm cố định. Chúng không nằm trong snapshot, không bắt được, không vào kho:

- **Cá nền:** 18 con. Chúng là **bóng mờ** màu xanh rêu đậm, độ trong suốt 22–34%, nhỏ hơn cá gameplay và không có sprite màu, nên không lẫn với cá thật. Chúng bơi qua lại trong quãng 8–26 m, nhấp nhô nhẹ và vẫy đuôi.
- **Bọt nước:** 22 hạt nổi lên rồi tan ở mặt nước.
- **Hiệu ứng bắn nước:** vòng bắn nước kéo dài 0,6 s khi bắt cá hoặc hái cây (từ event `fish_caught` và `gather`).
- **Vòng tầm bắt:** vòng nét đứt quanh Bà Út khi lặn, chuyển màu vàng khi có cá trong tầm và hết thời gian hồi.
- **Cá gameplay:**
  - quay đầu mềm: sprite lật qua 0 trong khoảng 0,1 s thay vì lật tức thì;
  - lắc thân ±0,05 rad và nhấp nhô ±1,4 px;
  - cây trên mặt nước dập dềnh nhẹ.
- Khi bật `prefers-reduced-motion`, các chuyển động trang trí đứng yên.

## 8. Hiệu năng

- Sprite và ảnh nền được tải một lần và dùng lại. Mỗi khung không tạo đối tượng mới, trừ trạng thái hoạt ảnh của từng cá; trạng thái này được dọn khi cá bị bắt.
- Số cá nền và bọt nước cố định, không sinh thêm vô hạn.
- **Đo trên trình duyệt** (1280×720, đang ở buổi sáng): `draw()` mất trung vị 0,5 ms, p95 0,6 ms mỗi khung. Con số này nhỏ hơn rất nhiều so với 16,7 ms của 60 FPS. Khung trình duyệt của app khi đo bị ẩn nên không đo được FPS thật.

## 9. Sửa thêm: ảnh lớn tải lỗi trên Windows

Khi kiểm tra, ảnh nền thường tải không xong. Tôi tái hiện được cả với `python -m http.server` chuẩn: file lớn hơn 255 KB hay kẹt ở đúng 261.120 byte qua loopback. Đây cũng là nguyên nhân của lỗi chập chờn `test_live.test_serves_phase_two_art`.

- **Cách sửa:** ghi phản hồi theo từng khúc 64 KB, trong `chonoi/live.py` (`_send`) và `docs/proof/phase-2/day_fixture.py` (`reply`).
- **Kết quả:** 12/12 lần tải `gather.webp` đủ dung lượng, `test_live` đạt 4/4 lần chạy liên tiếp.
- `chonoi/live.py` thuộc khung giảng viên cấp. Đây là thay đổi nhỏ, chỉ ở tầng HTTP, không đổi giao thức hay dữ liệu, và đã ghi lý do trong comment.
- Phía client có thêm cơ chế thử tải lại ảnh nền tối đa 3 lần.

## 10. Các file đã sửa

- `chonoi/interactive_world.py` (mới): giãn bản đồ theo `gather_world`.
- `chonoi/interactive.py`: gọi `world_tuning`; `InteractiveGather._move_fish` cho cá lượn tự nhiên.
- `chonoi/web/gameplay.json`: thêm `gather_world`.
- `chonoi/web/index.html`: camera, phép chiếu, nền nối dài, cá nền, bọt nước, hiệu ứng bắn nước, vòng tầm bắt, chỉ hướng bến, hoạt ảnh cá, nhãn vùng lũ không chạy ra ngoài khung.
- `chonoi/live.py`, `docs/proof/phase-2/day_fixture.py`: ghi ảnh theo khúc 64 KB.
- `tests/test_interactive_world.py` (mới): 6 test.
- `tests/test_interactive_menu.py`: test vị trí cây và cá sấu giờ so với bản đồ đã giãn (`world_tuning`) thay vì bản 100 m. Lý do: yêu cầu mới cố ý giãn tọa độ x ở bản web; số lượng, timer và luật vẫn được kiểm như trước.

## 11. Kiểm thử thực tế

**Trên trình duyệt** (khung app, 1280×720, bản web 5 ngày):

| Kiểm tra | Kết quả |
|---|---|
| Vượt biên cũ | Bơi tới x = 110 m rồi 196 m |
| Camera theo nhân vật | cameraX = 0,525 khi x = 110 m; dừng đúng 0,66 (max) ở biên phải; về 0 khi về bến |
| Nền | Đầu ca giống hệt ảnh cũ. Ở giữa là các dải nước nối dài, cuối sông là phần ảnh gốc có cây. Không có vùng đen hay mối nối lộ, không méo hình |
| Cá, cây, cá sấu khi camera di chuyển | Vẽ đúng chỗ theo camera; nhãn "Cá sấu · Tuần tra" đi theo con cá sấu |
| Tầm bắt | Bắt được cá lóc ở x ≈ 155 m (cá ở cách 1,8 m, `catch_radius` = 2) |
| Về bến | Từ 155 m về bến và cập bến mất khoảng 40 s, chuyển sang màn tối |
| HUD | Đồng hồ, oxy, máu và nhiệm vụ đứng yên; chỉ hướng bến hiện "◀ Bến 108 m" ở mép |

**Test tự động:**

- `tests/test_interactive_world.py`:
  - headless chuẩn vẫn 100 m;
  - bản đồ 200 m giữ số cá, số cây, số cá sấu, bến và yield;
  - cá rải qua vùng mới và luôn nằm trong biên;
  - cá đi được trung bình hơn 6 m trong 10 s, quay tối đa 1,5° mỗi tick khi không dội mép, và tất định theo seed;
  - bắt được cá ở x = 171,5 m;
  - cấu hình sai bị từ chối.
- **Regression:** `python -m unittest discover -s tests` cho **287/287 test đạt**.

## 12. Tốc độ bơi, chạy nhanh, dòng lũ và cá sấu

Chỉ áp dụng cho bản web 5 ngày; headless và `chonoi.live` giữ số chuẩn.

| | Chuẩn | Bản web |
|---|---|---|
| Bơi thường | 4 m/s | **6 m/s** (`swim_speed_multiplier` 1,5) |
| Giữ Shift khi bơi | — | **9 m/s** (`sprint_multiplier` 1,5) |
| Dòng lũ (ở độ sâu ≥ 10 m) | 1,5 m/s | **2 m/s** (`current_speed`) |
| Bơi thường ngược dòng lũ | 2,5 m/s | **4 m/s** (6 − 2) |
| Giữ Shift ngược dòng lũ | — | 7 m/s (9 − 2) |
| Cá sấu đuổi | 3 m/s | **7 m/s** (`monster_chase_speed`); tốc độ tuần tra vẫn 1 m/s |
| Giữ Shift khi đi trong Quán | — | 6 m/s (×1,5) |

- **Cấu hình** trong `chonoi/web/gameplay.json`: `gather_world.swim_speed_multiplier`, `gather_world.current_speed`, `gather_world.monster_chase_speed` và `sprint_multiplier`.
  - `world_tuning` kiểm phạm vi: hệ số bơi 1–5; tốc độ dòng lũ và cá sấu trong (0, 20] m/s; hệ số Shift 1–3.
- **Cân bằng:** cá sấu đuổi 7 m/s, nhanh hơn bơi thường (6) nhưng chậm hơn khi giữ Shift (9). Bị đuổi thì phải giữ Shift mới thoát được.
- **Code:** `SprintMixin` trong `chonoi/interactive.py`, nút `sprint` trong `chonoi/interactive_web.py`, các tốc độ ghi đè trong `chonoi/interactive_world.py`. Gia tốc ramp và biên bản đồ không đổi; chạy nhanh không tốn thêm oxy.
- **Test:**
  - `test_web_speeds_swim_6_sprint_9_against_current_4_croc_7`: kiểm các số ở bảng trên và headless vẫn 4 / 1,5 / 3;
  - `test_swimming_against_current_moves_4_mps`: mô phỏng bơi ngược lũ đi đúng 4,0 m trong 1 s;
  - `test_sprint_moves_faster_only_while_held`, `test_web_accepts_sprint_key_and_bad_multiplier_rejected`.

## 13. Hạn chế còn lại

- Dải nước nối dài là ảnh lật gương, nên nhà sàn và cây dừa ở chân trời lặp lại đối xứng và các tia nắng tạo hình chữ V ở mối nối. Không có vết hở, nhưng nhìn kỹ vẫn nhận ra họa tiết lặp lại. Muốn đẹp hơn cần thêm ảnh nền vẽ riêng cho đoạn giữa sông.
- Không có camera dọc: độ sâu 0–30 m vẫn vừa một khung như cũ.
- Cá nền dùng hình vẽ đơn giản (bóng mờ), không phải sprite.
- Chưa đo FPS thật khi cửa sổ hiển thị đầy đủ; chỉ đo được thời gian vẽ mỗi khung.
- `chonoi.live --mode gather` (chế độ chơi lẻ) vẫn là sông 100 m. Bản đồ dài chỉ có ở bản web 5 ngày.
