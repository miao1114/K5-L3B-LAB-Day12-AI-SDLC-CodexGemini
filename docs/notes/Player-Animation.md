# Sửa nhịp bơi/đi bộ của Bà Út

Status: **PASS** qua Chrome với simulation thật và HTTP polling.

## Thay đổi

- `chonoi/web/index.html`: thay nhịp sprite phụ thuộc trực tiếp quãng đường của
  từng snapshot bằng phase hoạt ảnh riêng cập nhật trong RAF. Tốc độ lấy từ
  chênh lệch vị trí/tick thực; nhịp chuẩn 10 FPS, scale theo `walk_speed` /
  `swim_speed` trong metadata. Đây là thông số trình bày, không đổi luật di chuyển.
- Canvas redraw khi nhân vật đang bước/bơi kể cả giữa các snapshot và khi
  nội suy vị trí đã kết thúc; không phụ thuộc việc khách có đang chuyển động.
- Giữ đúng atlas: đi bộ 5×3 (idle + 4 bước, trước/sau/ngang), bơi 3×2
  (glide + 5 stroke). Không thay ảnh, hướng lật, anchor hoặc code gameplay.
- Thả phím/chạm biên (vị trí không đổi) về idle; pause, đổi màn, lỗi và ẩn tab
  không tích lũy phase. Ngừng nhận snapshot quá cửa sổ jitter 180–300 ms
  thì dừng hoạt ảnh, tránh bước tại chỗ vô hạn khi mất dữ liệu.
- Tôn trọng reduced-motion như trước; không dùng tùy chọn **Khách đi bộ**
  để thay đổi animation của Bà Út. Controller, visual clock và state machine
  của khách tiếp tục độc lập.

## Bổ sung sau phản hồi vẫn bị cứng trên trình duyệt

Code trước vẫn buộc `motionFrame()` về 0 theo media reduced-motion, kể cả khi
người dùng đã bật **Khách đi bộ**. Không đọc được cài đặt trong tab Edge đang
chơi của người dùng, nên chưa kết luận đó là nguyên nhân duy nhất của phản hồi.

- Thêm **Hoạt ảnh Bà Út** dưới khung chơi, lưu `chonoi.playerMotion`.
  Mặc định theo hệ thống, nhưng lựa chọn bật rõ ràng có thể override media.
- Link `http://localhost:8783/?motion=on` bật và lưu cả hoạt ảnh Bà Út lẫn khách
  trong profile trình duyệt mở link; không reset tiến trình game ở server.
- Nội suy vị trí dùng cùng tùy chọn hoạt ảnh Bà Út; tăng trần cửa sổ nội suy
  từ 100 lên 200 ms để hấp thụ polling chậm, không đổi snapshot/vận tốc backend.
- Kiểm tra thêm đúng `InteractiveDayWeb` + HTTP adapter đang dùng cho gameplay
  mở rộng, **Microsoft Edge thật**, reduced-motion bật giả lập. Dùng phím thật
  qua UI để bắt đầu Gather / cập bến / chuyển Quán. Scenario cấp sẵn kho cá lóc
  cho ca Quán, không sửa luật kết thúc hay tốc độ để kiểm thử.
- Lệnh: `.venv/Scripts/python.exe tools/verify_player_day_browser.py`.
  **4/4 checks PASS**: bơi và đi bộ đổi nhiều sprite dù media đang reduce;
  tắt riêng Bà Út trở lại idle mà tùy chọn khách vẫn bật. Không JavaScript exception.
- Chạy lại bộ Player **15/15 PASS**, NPC **32/32 PASS** sau thay đổi.
  Proof Edge: `docs/proof/player-animation/edge-day-verification.json`,
  `edge-day-gather-motion-on.png`, `edge-day-quan-motion-on.png`.

## Kết quả kiểm chứng

```powershell
.venv/Scripts/python.exe tools/verify_player_animation.py
.venv/Scripts/python.exe tools/verify_npc_walk.py
```

- Player: **15/15 checks PASS**, không có JavaScript exception.
  Đủ 4 khung bước / 5 khung bơi; ít nhất 8 thay đổi pose trong cửa sổ 1.05 giây
  khi di chuyển ở tốc độ bình thường. Đã kiểm tra idle, đổi hướng, phase giữa
  snapshot, pause, reduced-motion và stale snapshot.
- Có ca **Bà Út đang đi và khách đang entering đồng thời**: cả phase Bà Út và
  vị trí khách đều tiến triển độc lập trong cùng Canvas với simulation thật.
- Regression khách: **32/32 checks PASS**, gồm vào bàn, ngồi, ăn/uống, đi ra,
  pause, restart, reduced-motion/override và sinh khách từ backend thật.
- Bằng chứng: `docs/proof/player-animation/verification.json`,
  `quan-moving.png`, `gather-moving.png`; báo cáo NPC tại
  `docs/proof/npc-walk/verification.json`.
- Fixture kiểm tra đồng thời được cấp kho cá lóc để backend có nguyên liệu
  sinh order; không thay tuning hoặc luật sinh khách để làm test pass.
- Không chạy benchmark, soak hoặc toàn bộ headless. Không sửa backend,
  contract, tốc độ/timer/đơn hàng/doanh thu. Không commit/push/merge.

Tab đã mở cần Ctrl+F5 tại `http://localhost:8783` để chạy JavaScript mới.
