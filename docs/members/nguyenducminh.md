# miao1114 — Nguyễn Đức Minh — phản tư cá nhân

- **Tôi đã làm (có Codex hỗ trợ):**
  - P1-04: nấu, lấy món, phục vụ, thanh toán, boa và cleanup đơn: [1e7e6c6](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/1e7e6c6).
  - P2-04: hai bếp, bốn bàn, sáu món; nấu song song và tương thích Day Loop: [d505e17](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/d505e17).
  - P3-04: tiêu đúng ID nguyên liệu, chốt giá theo độ tươi; tích hợp kho của người 3: [1bb2752](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/1bb2752), [ebc737e](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/ebc737e).
  - Web: nhiệm vụ ngày, stack cá linh, Auto End Quán, DayResult, Shop thật; mở khóa món và sinh nguyên liệu theo ngày: [d8222c4](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/d8222c4).
- **Tôi đã kiểm tra/review:** Luồng bắt cá–bàn giao kho–nấu–thu tiền, độ khó nhiệm vụ và tích hợp main. Bằng chứng: [250 regression, 34 targeted và Chrome](../notes/Menu-Unlock-Resource-Spawn.md). Chưa ghi nhận liên kết review PR độc lập.
- **AI sai ở đâu và tôi phát hiện thế nào:** Nhiệm vụ nhiều bông súng, Gather sinh nguyên liệu ngoài menu, demo chưa nối Shop. Tôi phản hồi khi chơi thử và yêu cầu sửa, kiểm chứng lại.
- **Điều tôi học được:** Tách gameplay web khỏi headless chuẩn; kiểm tra công thức, ID, thứ tự tick và tiền bằng test biên, replay và trình duyệt.
