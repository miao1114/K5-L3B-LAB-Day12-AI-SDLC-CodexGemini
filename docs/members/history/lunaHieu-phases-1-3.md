# lunaHieu — phản tư cá nhân Phase 1 (Người 2)

- **Tôi đã làm:** Đặc tả Lát 2 ([b51820a](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/b51820a7a490180a7369caa7c59a0d9d96a07188)), triển khai hái/bắt/giỏ đầy ([79d3e92](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/79d3e92f2e289694c326fc029ae6d13ac6929fd5)), viết test và bằng chứng ([47e33c7](https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini/commit/47e33c75605a33d907b25ad629eeb05e6156c005)). Link hoạt động sau khi push. Bổ sung README.
- **Tôi đã review:** Đọc PRD-0, Test Contract, `AGENTS.md`, hợp đồng kho và kiểm `git diff chonoi/sim/gather.py`: code chỉ đổi hai khối TODO Lát 2. Chưa review PR của người khác.
- **Kết quả kiểm chứng:** Lượt chạy toàn suite có 47 test, 46 đạt, 1 thất bại (`$LASTEXITCODE = 1`); 14/15 test Lát 2 đạt. Output thật ở [`../proof/phase-1/gather-collection-test.txt`](../proof/phase-1/gather-collection-test.txt).
- **Cần phối hợp:** Người 1 xử lý `choke`/`faint`, lưu `lost` theo LIFO và xóa giỏ trước `gather_end`. Chạy lại suite sau khi tích hợp.
- **AI sai ở đâu:** Codex từng thêm helper `_nearest()` ngoài hai khối TODO được giao; tôi phát hiện qua `git diff` và đã hoàn tác trước khi triển khai. Tôi học được cách chốt ranh giới sửa file và kiểm chứng cả event, file kho lẫn mã thoát.

## Phase 2 — P2-02: Monster, HP & Survival

- **Tôi đã làm:** Viết [đặc tả P2-02](../plan/phase-2.md); tách logic Cá Sấu Năm Chèo vào `chonoi/sim/monsters.py`, nối hook vào Gather, bổ sung validation `gather.monsters[]` và test `tests/test_monster_survival.py`. Hỗ trợ spawn theo ngày, tuần tra/đuổi, hit rơi đồ LIFO, recoil, ngất, snapshot và trần oxy/HP theo `active_upgrades`.
- **Tôi đã review:** In toàn bộ `git diff` tracked và đối chiếu trực tiếp các điểm biên: recoil bắt đầu bước sau, tick hết recoil không hit, tách `lost` của hit và ngất, snapshot quái sắp ID. Test Phase 1 về bất tử/ngạt được cập nhật vì luật v1.1 quy định ngạt xuyên bất tử và không làm rơi hàng.
- **Kết quả kiểm chứng:** Toàn suite **80/80 đạt, exit 0**; [ma trận AC](../verification/phase-2.md) và [output test thật](../proof/phase-2/monster-survival-test.txt). Chưa commit nhánh `feat/p2-monster-survival`.
- **Cần phối hợp:** Người 1 cập nhật manifest v1.1; Người 3 truyền `day`/`active_upgrades` từ vòng ngày và kiểm snapshot chung. Sau khi ghép, chạy lại toàn suite và kiểm tra conflict ở `gather.py`/`scenario.py`.

## Phase 3 — P3-02: Inventory Schema & Day Adapter

- **Tôi đã làm:** Viết [đặc tả AC-P3-I2-01..06](../plan/phase-3.md); thêm `IdRegistry` cấp ID `I1...` không tái dùng, kiểm/ghi nguyên tử file kho cá thể v1.2, validate scenario và adapter giữ nguyên `id/kind/fresh` khi Gather bàn giao cho Quán trong Day Loop. Cập nhật manifest và mẫu kho; CLI headless từ chối file đếm cũ với mã 2.
- **Kết quả kiểm chứng:** **152/152 test đạt, exit 0**; [ma trận AC](../verification/phase-3.md) và [output thật](../proof/phase-3/inventory-v12-test.txt). Các test Phase 1/2 về file kho và snapshot Day được đổi kỳ vọng theo breaking change v1.2.
- **Cần phối hợp:** P3-01 áp dụng hao tươi theo tick; P3-03 chọn cá thể khi nấu và hoàn thiện kho Quán. Repo chưa có hợp đồng v1.2 trong `docs/contracts/`, nên nhóm cần xác nhận tên khóa tuning độ tươi đã ghi trong spec/manifest.
