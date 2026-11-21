# P4-C — Warning System & High Contrast

**Status: COMPLETE.** Nhánh `updatelevel`, HEAD `9919bca`. Chưa commit/push.
Chỉ sửa frontend và thêm verifier/proof/notes; giữ các sửa P4-B, TEAM, manifest
và reflection đang có trong working tree. Không sửa verification chung của P4-D.

## A. Audit

Đối chiếu AGENTS, README, HTML/CSS/Canvas, snapshot Gather/Quán và live server.

| Tính năng trước sửa | Phân loại | Nhận xét |
|---|---|---|
| Cá sấu | PARTIAL | Hint báo chase, chưa xét khoảng cách và chưa có banner |
| Oxy | PARTIAL | HUD đổi màu tại ≤25%, chưa có cảnh báo chữ nổi bật |
| Trạng thái khách Canvas | WORKING | Waiting xanh, eating vàng, danger đỏ ở ≤20%, có chữ/biểu tượng |
| Sidebar khách | PARTIAL | Ngưỡng đỏ 25%, lệch Canvas 20%; chưa có banner ưu tiên bàn |
| High Contrast/settings | MISSING | Chưa có nút, palette Canvas hoặc lưu lựa chọn |

Snapshot đã đủ player.pos/oxygen/max/hp/at_surface, monsters.pos/state/kind,
meta.monsters.species.detect_radius, customers.state/table_id/patience và meta timer.
Không cần bổ sung trường API hay sửa backend.

## B. Implementation

- `chonoi/web/index.html`: thêm `warningsFor` chỉ đọc snapshot và vùng cảnh báo
  HTML ngoài Canvas, dưới HUD; dùng chung vùng thay vì tạo banner theo từng cá sấu.
- Cá sấu: Euclid theo **tọa độ thế giới**, dùng detect_radius đúng species từ
  snapshot; fallback UI 12 m khi thiếu config. Chỉ xét patrol/chase/recoil;
  không xét dead/inactive/defeated/stunned. Lấy cá sấu gần nhất để quyết định một
  cảnh báo chung “CẨN THẬN! CÁ SẤU Ở GẦN!”. Không sửa AI/hit/radius gameplay.
- Oxy: ≤25% max thật, chỉ khi đang dưới nước, còn sống và ca chưa kết thúc.
  “SẮP HẾT OXY! HÃY NỔI LÊN!”. Dùng lại helper ngưỡng cho HUD, không hard-code
  450 tick; bình nâng cấp cũng dùng đúng tỷ lệ. Hồi trên ngưỡng/nổi/ngất thì gỡ.
- Khách: chỉ waiting, patience/max ≤20%; thống nhất sidebar với Canvas hiện có.
  Chọn bàn có ít tick còn lại nhất, hòa theo tên bàn; hiện “BÀN Tx SẮP BỎ ĐI!”.
  Eating/đã rời không giữ cảnh báo. Không thay timer hoặc cơ chế phục vụ.
- Ưu tiên oxy trước cá sấu; Quán chỉ một bàn khẩn cấp. Các hàng nằm trong grid,
  không overlay lên nhân vật/bếp/bàn. Chuyển flow scene, finished/error hoặc mất
  điều kiện sẽ ẩn. Pause giữ cảnh báo tình huống hiện tại, không tự đếm timer.
- Nút “Tương phản cao: Bật/Tắt” nằm ở header, dùng aria-pressed, bàn phím native.
  Lựa chọn lưu `chonoi.highContrast` bằng localStorage có try/catch; khi bị chặn
  vẫn bật/tắt trong phiên. Không gửi thay đổi preference vào backend.
- CSS dùng attribute/palette: cảnh báo nền đặc, chữ trắng/viền vàng; HUD, bảng,
  progress, focus dễ đọc. Không đổi ảnh nền hoặc sprite.
- Canvas tái sử dụng `drawCustomerBar`, thêm palette high contrast và viền trắng,
  giữ chữ Đang chờ/Đang ăn/⚠ Sắp bỏ đi. Toggle invalidate Canvas ngay; tắt pulse
  ở high contrast, vẫn tôn trọng prefers-reduced-motion. Không sửa animation.
- Vùng cảnh báo dùng role=status, aria-live polite; setHTML cache chỉ cập nhật
  khi nội dung đổi, tránh thông báo lặp mỗi frame. Không có hiệu ứng chớp mới.

## C. Verification

Lệnh thực tế (Python `.venv`, Playwright + Chrome đã có trên máy):

```powershell
$env:PYTHONUTF8 = '1'
.venv\Scripts\python.exe tools/verify_p4_c.py
.venv\Scripts\python.exe -m unittest discover -s tests -p test_live.py -v
.venv\Scripts\python.exe tools/verify_p3_05_browser.py docs/proof/phase-4/p4-c/regression-ui
```

- **8 focused tests PASS**, 9.772 s; logic cảnh báo, ngưỡng, nhiều thực thể,
  lifecycle, pause/resume, theme, reload, localStorage bị chặn, reduced motion,
  không mutate snapshot, bố cục/contrast và ảnh thật.
- **3 live regression tests PASS**, 1.249 s: state, input, restart, itemized basket, assets.
- **PASS** browser regression: WASD/Space/E/R; nhiều khung bơi và bước chân;
  dừng/thay hướng; HUD và sprites tại 1440/1024/768/390 px.
- Không pageerror/console error trong nhóm P4-C. Không chạy lại full suite,
  benchmark hoặc soak 10 ngày vì task chỉ đổi UI.

Tất cả UI test P4-C dùng viewport **1280×720**, HTTP localhost thật. Snapshot
fixture tạo từ LiveGame/GatherSim/QuanSim thật; chỉ override `/state` trong browser
test để tái hiện ranh giới, không có endpoint debug trong sản phẩm. Ảnh full-page
có thể cao hơn viewport do sidebar Quán dài; không tuyên bố mọi nội dung nằm gọn
trong 720 px. Đã kiểm vùng cảnh báo tách khỏi HUD/Canvas, không tràn ngang.

| AC-P4-C | Trạng thái | Bằng chứng |
|---|---|---|
| 01 | PASS | Cá sấu gần/ngưỡng inclusive hiện banner |
| 02 | PASS | Cá sấu xa gỡ banner |
| 03 | PASS | Bỏ state dead/inactive/defeated/stunned |
| 04 | PASS | Hàm thuần không mutate snapshot; không sửa simulation |
| 05 | PASS | Oxy 450/1800 hiện cảnh báo dưới nước |
| 06 | PASS | 451/1800 và nổi lên không cảnh báo |
| 07 | PASS | Bình 2700 tick cảnh báo đúng tại 675 |
| 08 | PASS | Không sửa timer/hao/hồi; chỉ đọc snapshot |
| 09 | PASS | Waiting ≤20% hiện cảnh báo |
| 10 | PASS | Đúng T2; T1 còn ít hơn thì ưu tiên T1 |
| 11 | PASS | Eating T3 không cảnh báo, kể cả patience cũ thấp |
| 12 | PASS | Served/eating hoặc xóa customer thì gỡ |
| 13 | PASS | Toggle nhiều lần, aria-pressed và redraw đúng |
| 14 | PASS | Ảnh monster high contrast |
| 15 | PASS | Ảnh oxygen high contrast |
| 16 | PASS | Ảnh customer high contrast; có fill Canvas palette mới thực tế |
| 17 | PASS | Gather→Quán, pause/resume và reload giữ preference |
| 18 | PASS | Code chỉ frontend; dữ liệu đầu vào không mutate; live regression |

Đo theo công thức relative luminance sRGB, lưu `contrast-ratios.json`:

| Thành phần | Tỷ lệ |
|---|---:|
| Chữ banner thường / nền đặc | 13.46:1 |
| Chữ high contrast / nền đen | 21:1 |
| Viền vàng / nền đen | 19.56:1 |
| Canvas wait / nền đen | 15.30:1 |
| Canvas eat / nền đen | 19.56:1 |
| Canvas danger / nền đen | 7.57:1 |

Đây là kiểm các cặp màu cảnh báo/thanh trạng thái, không phải chứng nhận WCAG cho
toàn website. Cảnh báo luôn có chữ/biểu tượng, không phụ thuộc riêng màu sắc.

Proof mới riêng tại `docs/proof/phase-4/p4-c/`, không ghi đè proof P4-B/thành viên khác:

- `browser-tests.txt`, `live-tests.txt`, `animation-hud-regression.txt`, `contrast-ratios.json`.
- `warning-monster-normal.png`, `warning-monster-contrast.png`.
- `warning-oxygen-normal.png`, `warning-oxygen-contrast.png`.
- `warning-customer-normal.png`, `warning-customer-contrast.png`.
- `regression-ui/`: ảnh HUD/sprite hồi quy.

## D. Remaining issues / bàn giao P4-D

Không còn lỗi P0 được phát hiện trong phạm vi này. Chưa có đánh giá bằng screen
reader thật hoặc WCAG toàn trang; layout cũ Quán có thể cần cuộn dọc. Không thêm
hysteresis vì chưa thấy nhấp nháy đáng kể; banner cập nhật trực tiếp theo snapshot.

P4-D dùng bảng AC và thư mục proof trên để cập nhật `docs/verification/phase-4.md`.
Task này không sửa manifest, README, verification chung hoặc P4-A/P4-B; mọi thay
đổi backend trong git status thuộc P4-B/lượt trước và giữ nguyên. Chưa commit/push.
Refresh trang game để nhận UI mới, nút tương phản cao nằm ở header.
