# Quán Ăn Chợ Nổi v1.0.0 — ứng viên, chưa công bố

Game Python/Canvas của CodexGemini: Gather bắt cá/hái rau, cá sấu và sinh tồn;
Quán hai bếp/bốn bàn/sáu món; vòng ngày/Shop, kho cá thể và giá theo độ tươi.
Phase 4 thêm benchmark render, soak 10 ngày, cảnh báo và High Contrast.
Web mở rộng có camera/map 200 m, animation, stack linh, menu unlock và nhãn bàn.

## Chạy từ ZIP

Giải nén, vào thư mục quan-an-cho-noi, chạy với Python đã cài:

```bash
python3 -m chonoi.live --mode day --days 5 --port 8783
```

Mở http://127.0.0.1:8783/. WASD/mũi tên, Space bắt cá, E tương tác,
P/Esc pause; Shop mua nâng cấp hoặc rời; High Contrast ở header.

## Kiểm chứng

- Benchmark: avg60.0015, p1 low53.6269, load964.65ms, 1801 frame/30.0159 s.
- Soak v1.3: hai lượt 10/10 ngày, 0 crash, deterministic trừ duration_s.
- Regression: 303/304 lượt full; lỗi version cũ được sửa theo inheritance,
  nhóm Quán chạy lại 22/22 PASS. Không tuyên bố đã chạy full lại.
- UI: 8 test warnings/accessibility, 3 live và animation/HUD PASS.
- Package/clone: PASS trên Chrome/Windows, ứng viên d251401; xem
  docs/proof/phase-4/p4-d/package-report.json. Linux/macOS chưa kiểm.

## Giới hạn

Chưa nghiệm thu Linux/macOS và chưa đủ reflections. Không có tag/Release công khai
ở thời điểm soạn. Benchmark phụ thuộc máy; soak input trung tính. Kho đếm cũ không
tương thích v1.2/v1.3, cần items[] với ID/fresh.

## Credits

CodexGemini (6 thành viên), mã nguồn MIT. Người dùng xác nhận ảnh do mình tạo AI;
xem CREDITS/LICENSE, tuân thủ điều khoản công cụ. Không nhúng font/audio bên ngoài.
