# TEAM

**Tên nhóm:** CodexGemini  **Số người:** 6 (khớp `team_size` trong `game.contract.json`)

**Dự án:** Quán Ăn Chợ Nổi — VinUni AI20k, Day 12 AI SDLC Lab.

**Repository:** [K5-L3B-LAB-Day12-AI-SDLC-CodexGemini](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini).

**Cách tổ chức:** Chia theo module, làm song song trên fork chung; tích hợp, kiểm thử và ghi bằng chứng đóng góp thực tế.

| Thành viên | GitHub handle | Module chính | Vai quy trình | Người dự phòng cho |
|---|---|---|---|---|
| Đoàn Công Hải | rawser246 | `sim/gather`, di chuyển, lặn/nổi, oxy, máu và sinh tồn | Phụ trách module Gather/sinh tồn; kiểm thử module và phối hợp tích hợp ([ghi chép](docs/members/doanconghai.md)) | (chưa chốt) |
| Nguyễn Văn Hiếu | lunaHieu | `sim/gather`, thu thập, quái và adapter kho | Phụ trách module; hỗ trợ tích hợp | (chưa chốt) |
| Lê Huy Anh | hann1holic | `sim/quan`, khách/kho, Day Loop, Shop | Phụ trách module; hỗ trợ hợp đồng tích hợp | (chưa chốt) |
| Nguyễn Đức Minh | miao1114 | `sim/quan`, Kitchen & Serving, freshness pricing; gameplay web | Integrator; Release Phase 4 là đề xuất | (chưa chốt) |
| Phạm Thế Hùng | thehung1406 | `client/ui`, HUD, hình ảnh, hoạt ảnh và QA | UI/QA; QA lead chưa chốt | (chưa chốt) |
| Đào Ngọc Ánh | daoanh9503 | Chức năng mở rộng; hoàn thiện gameplay, UI và UX | Phụ trách mở rộng; hỗ trợ tích hợp và kiểm thử trình duyệt | (chưa chốt) |


**Vai quy trình:** PO (đầu mối hỏi giảng viên, giữ `docs/clarify.md`) · Integrator (giữ `docs/contracts/`, gắn tag) · QA lead · Scrum/Release. Có thể kiêm.

## Thỏa thuận làm việc nhóm (điền trong 15 phút kickoff, ≤ 10 dòng)

- Kênh liên lạc: Zalo; báo ngay blocker, test lỗi hoặc mâu thuẫn contract.
- Khi bất đồng về thiết kế: thảo luận ngắn; người tích hợp chốt quyết định và ghi lý do.
- Khi ai đó trễ hoặc vướng quá 10 phút: báo nhóm để phối hợp; người dự phòng cụ thể chưa chốt.
- Giờ standup giữa phase: nhóm cần xác nhận; trao đổi ngắn trước mỗi mốc tích hợp.
- Cách đọc code của nhau: đối chiếu diff/PR và contract ở ranh giới module; chỉ ghi review khi thực sự đã làm.
- Cách làm việc với Git: ưu tiên nhánh task ngắn, không force-push hoặc ghi đè thay đổi của nhau; người gắn tag do nhóm xác nhận.
- Tích hợp: hạn chế sửa đồng thời manifest, README, entrypoint, hợp đồng và verification chung.
- Kiểm thử: chạy targeted test theo task, regression trước bàn giao; không khai PASS khi chưa chạy.
- Đồng tác giả: khi cùng làm một commit, ghi trailer `Co-authored-by:` đúng người đóng góp.
