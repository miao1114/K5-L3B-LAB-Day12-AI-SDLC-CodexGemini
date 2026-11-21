# hann1holic — Phản tư cá nhân

**Lê Huy Anh**

## Tôi đã làm

- **Phase 1.** Xử lý khách đến, đặt món, giữ nguyên liệu và hoàn trả khi khách hết kiên nhẫn. [Commit `5bcbbda`](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/5bcbbda204d7c9e26c8a761f341a42721cb25bdd)
- **Phase 2.** Triển khai vòng ngày headless, thực đơn D1–D5, bàn giao kho, Shop và pause. [Commit `eb7debb`](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/eb7debba20eb828f637d9b85533d0b875d236b15)
- **Phase 3.** Quản lý kho Quán theo ID, hao tươi và thử giữ lại nguyên liệu khi hàng ươn. Bản ghép qua 201 test. [Commit `547d00c`](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/547d00c6eddaa28eb4044da6d6d4fa91a515ab4f) · [Bằng chứng](../proof/phase-3/quan-stock.md)

## Tôi đã review

Tôi dùng Codex đối chiếu hợp đồng kho và đơn hàng khi ghép Quán với Bếp, gồm ca phục vụ đúng tick khách hết kiên nhẫn. [Commit tích hợp `1cbad3a`](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/1cbad3a5b914f21292271b6ad5dbd5f444ea9bd9)

## AI sai ở đâu và tôi phát hiện thế nào

Bản đầu của Codex ghi tồn khả dụng vào snapshot và cho khách rời trước tương tác. Đối chiếu PRD-0 mục D–F cho thấy snapshot cần ghi tồn vật lý và khách rời sau tương tác. [Nhật ký AI](../ai-usage-log.md)

## Điều tôi học được

Tôi cần kiểm thử thứ tự xử lý trong cùng một tick, như khi giao món đúng lúc khách hết kiên nhẫn.
