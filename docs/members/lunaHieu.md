# lunaHieu — phản tư cá nhân (≤ 200 từ)

Nguyễn Văn Hiếu — MSSV 2A202603746.

- **Tôi đã làm (kèm link commit):** Phase 1, tôi đặc tả và triển khai hái cây, bắt cá, giỏ đầy ([79d3e92](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/79d3e92)). Phase 2, tôi viết logic cá sấu, hit/recoil và ngất ([dcbf337](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/dcbf337)). Phase 3, tôi làm ID nguyên liệu xuyên ngày, schema kho cá thể, ghi nguyên tử và bàn giao Gather → Quán ([8ae75ca](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/8ae75ca)).
- **Tôi đã review (kèm link):** Khi ghép code cá bơi của Người 1 với phần quái của tôi, `gather.py` bị conflict. Tôi đối chiếu hai nhánh với Test Contract, giữ thứ tự tick và chạy lại 130 test ([merge commit 415c9b1](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/415c9b1)). Tôi chưa review PR độc lập.
- **AI sai ở đâu và tôi phát hiện thế nào:** Codex thêm helper `_nearest()` ngoài hai khối TODO được giao. Tôi thấy thay đổi đó trong `git diff` và hoàn tác trước khi triển khai.
- **Điều tôi học được:** Cần kiểm phạm vi sửa và hợp đồng khi ghép code song song; chỉ báo đạt sau khi kiểm event, file kho, test và mã thoát. [Ghi chép theo phase](history/lunaHieu-phases-1-3.md).
