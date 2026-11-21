# daoanh9503 — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm (kèm link commit):**
  - Dòng nước lũ và khách đặt trước trong bản web 5 ngày; khách đặt trước chỉ gọi món đã mở khóa: [83baf55](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/83baf55).
  - Thanh chờ/ăn/sắp bỏ đi trên đầu khách, nhãn "MANG TỚI Tx" khi cầm món, sidebar không nhảy: [48f132c](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/48f132c).
  - Sông Gather 200 m, camera theo Bà Út, cá bơi tự nhiên, giữ Shift chạy nhanh, chỉnh tốc độ (bơi 6, chạy 9, ngược lũ 4, cá sấu 7 m/s); sửa lỗi ảnh lớn tải không xong trên Windows. Phần này chưa commit; xem `docs/notes/Gather-Map-Expansion.md`.
- **Tôi đã review:** gộp `main` (PR #13, #14) vào code của mình, xử lý conflict `index.html`; kiểm chứng trên trình duyệt và chạy toàn suite (291/291).
- **AI sai ở đâu và tôi phát hiện thế nào:**
  - Sau khi gộp `main`, 3 test lỗi vì `InteractiveDaySim` thiếu `reservations`; phát hiện qua test.
  - Biển đặt trước đè lên nhãn bàn; phát hiện qua ảnh chụp trình duyệt.
  - Ảnh nền mất do Windows kẹt khi gửi file lớn hơn 255 KB; tái hiện bằng `curl`.
- **Điều tôi học được:** kiểm chứng UI trên trình duyệt, không chỉ tin test; giữ headless tách khỏi tính năng web.
