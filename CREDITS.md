# Credits

- Xác nhận của người phụ trách trong phiên tích hợp P4-D: toàn bộ ảnh nhóm cung cấp
  (kể cả các ảnh từng được gọi là “Ảnh lab”) do người dùng tự tạo bằng AI, không phải
  asset tải từ Stardew Valley. Các tên file bên dưới mô tả nguồn đầu vào nội bộ.
- Nhóm chọn MIT cho mã nguồn, xem LICENSE. Xác nhận AI không thay thế điều khoản
  của nhà cung cấp công cụ; không tự gán giấy phép bên thứ ba cho ảnh. Nhóm cần giữ
  nguồn gốc/prompt và tuân thủ điều khoản công cụ khi phân phối ảnh.
- Font: dùng font hệ thống Cambria/Times New Roman/system-ui/sans-serif, không nhúng
  file font. Chưa có âm thanh ngoài. Runtime Python dùng thư viện chuẩn; Playwright
  (Apache-2.0) và Chrome/Chromium là phụ thuộc kiểm thử cài riêng, không kèm ZIP.
Liệt kê asset ngoài (nguồn, giấy phép CC0/CC-BY/MIT) và công cụ AI đã dùng.

- Phase 1 frontend: pixel art Canvas 2D và biểu tượng SVG nội tuyến được tạo cho dự án bằng Codex. Không dùng ảnh, font hay âm thanh từ bên ngoài.
- Hướng mỹ thuật tham khảo không khí ấm áp của Stardew Valley. Sprite, cảnh và giao diện được vẽ riêng cho Quán Ăn Chợ Nổi.
- Phase 2 dùng ảnh do nhóm cung cấp trong thư mục Ảnh lab. Hai cảnh dùng `BackGroundGather.png` và `BackgroundQuans.png`. Sprite lấy từ `BaUT.png`, `CaSau.png`, `Khachnam.png`, `Khachnu.png`, `Ca1.png` và `Ca2.png`. Sáu ảnh món dùng cho thực đơn, đơn hàng và bếp. Các bản WebP nằm trong `chonoi/web/art/`, tên món theo `dish_id`.
- Tư thế bơi của Bà Út dùng `ảnh bơi.png` từ cùng thư mục, xuất thành `ba-ut-boi.webp`.
- Phase 3 tách sáu sprite WebP trong suốt từ `BackgroundQuans.png`. Nền `quan-nen.webp` dùng ImageGen để bỏ hai bếp và bốn bàn, lấp lại sàn gỗ và vách tre theo ảnh gốc.
- Sprite `ba-ut-di-bo.webp` dùng ImageGen từ hình Bà Út của nhóm. Ba hàng là chính diện, quay lưng và nhìn ngang. Mỗi hàng gồm một dáng đứng và bốn khung bước, căn theo bàn chân.
- Sprite `ba-ut-nhip-boi.webp` dùng ImageGen từ tư thế bơi của nhóm, gồm một dáng lướt và năm khung quạt tay, đạp chân nhìn ngang.
- NPC Walk-In: nhóm cung cấp bốn spritesheet AI `khach-nam-di-bo.webp`,
  `khach-nu-di-bo.webp`, `khach-nam-ngoi.webp`, `khach-nu-ngoi.webp`.
  Dùng trực tiếp ảnh WebP, không dùng hai PNG ngồi kèm bàn và không tạo thêm bàn.
