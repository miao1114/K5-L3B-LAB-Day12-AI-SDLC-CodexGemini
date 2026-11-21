# ADR-003 — Breaking Change: Count Inventory → Itemized Freshness Inventory

- **Status:** PROPOSED — cần nhóm xác nhận trước khi merge/tạo tag.
- **Phase:** 3 · TICKET-03 · Test Contract v1.2.
- **Owners đề xuất:** P3-02 chốt schema/adapter; P3-01 Gather; P3-03 Quán reservation; P3-04 Kitchen; P3-05 UI/QA.
- **Nguồn quyết định:** `docs/specs/TICKET-03_original.md`.

## 1. Bối cảnh và động lực

V1.1 dùng kho số lượng theo kind (`{"items":{"ca_loc":1}}`). V1.2 thay bằng cá thể có ID và độ tươi riêng để theo dõi hao tươi, mất hàng LIFO, giữ chỗ và tính giá lúc vào bếp. Đây là **breaking change bắt buộc**, không phải đề xuất lựa chọn.

## 2. Quyết định theo yêu cầu chính thức

1. Kho v1.2 có root chỉ `items` và mảng object `{id,kind,fresh}`; `gather.hold`, `quan.stock`, `shop.stock` dùng mảng item; `customers[].reserved` dùng list IDs.
2. `contract_version:"1.2"` từ chối kho đếm và fixture sai với exit code 2.
3. Fresh mới là 100; Gather -0.5/s; Quán -0.25/s; ươn khi fresh <30; pause không decay; món chín không decay.
4. IDs `I1,I2,...` tăng theo thứ tự nhặt xuyên ngày; không tái sử dụng khi đã tiêu hoặc mất.
5. Kho quán re-reserve theo ID khi một phần giữ ươn; chốt giá ở `cook_started` theo độ tươi trung bình item thực sự tiêu.
6. Bàn giao file và day trong cùng tick, không hao thêm; file atomic khi có gather_end; fainted xuất kho rỗng.

## 3. Tác động và phân công (đề xuất nhóm)

| Mảng | Thành phần/file cần tra trong repo thật | Breaking impact | Chủ trách nhiệm | Test cần đổi/thêm |
|---|---|---|---|---|
| Manifest | `game.contract.json` | v1.2 + freshness object | P3-02 | manifest validation |
| Shared inventory | file đọc/ghi kho, adapter, serializers | object đếm → item array; exit2 | P3-02 | valid/invalid/atomic/no write |
| Gather | `chonoi/sim/gather.py` + helpers | hold objects, freshness, lost LIFO | P3-01 | spoil threshold/dock/faint/hit |
| Quán stock | `chonoi/sim/quan.py` + helpers | stock decay, reserved IDs, re-reserve | P3-03 | stock selection/expired order |
| Kitchen | `chonoi/sim/quan.py` + helpers | consume IDs, price, cook event | P3-04 | tick1 price, 2 stoves, payment |
| Day/Shop | day dispatcher/state/scenario | IDs xuyên Ngày, no transfer decay, Shop stock | P3-02 + P3-03 | day 1/2, Shop snapshot |
| JSONL/headless | event/snapshot output | item arrays, spoiled, sort/precision | P3-02 + các owner | snapshot/event shape |
| Web local | `chonoi/web/index.html`, asset khác nếu có | HUD freshness/spoiled | P3-05 | local render smoke |
| Docs | `CHANGELOG.md`, verification, proof | ghi breaking, hồi quy, bằng chứng | Cả nhóm | review checklist |

**Ghi chú:** Đường dẫn helper chưa biết phải được xác nhận qua working tree; đây là danh sách vị trí cần kiểm, không khẳng định code hiện tại đã có module đó.

## 4. Phương án tích hợp không làm gãy main

- **A — Chốt contract:** Các member thống nhất cấu trúc Item, allocator, owner của `step()` và hợp đồng người 3/4; thêm fixture canonical.
- **B — Chuẩn bị đường chạy v1.2 trên nhánh:** Adapter/serializer + validator + scenario/snapshot phải có test. Có thể giữ adapter v1.1 tạm trong nhánh trước khi bật manifest v1.2.
- **C — Triển khai các lát song song:** Gather; Quán stock/re-reserve; Kitchen price; UI. Test theo fixture nội bộ, mock ranh giới đã chốt.
- **D — Tích hợp:** Ghép các lát, chạy smoke file->Quan và day; chỉ **sau khi cả đầu ghi/đọc đều đúng** mới đặt `contract_version:"1.2"` và gộp code vào main làm bản bàn giao.
- **E — Regression và tag:** Test v1.2; test P1/P2 còn hiệu lực; ghi lý do đổi fixture cũ; cập nhật docs, tag `phase-3` đúng hạn.

Không dùng “fallback nhận kho đếm” trên final v1.2 để qua test mà thực chất vi phạm contract.

## 5. Rủi ro, trade-off và kế hoạch kiểm thử

| Rủi ro | Hậu quả | Phòng ngừa / Test |
|---|---|---|
| Sinh ID ở nhiều module | trùng ID xuyên Ngày | allocator single source; day two-days fixture |
| Serialize rounding fresh | sai spoiled/price tại ngưỡng | test fresh=30, exact floor tick1 |
| Re-reserve sau cook | nấu hàng vừa ươn | assert spoiled → re-reserve → cook |
| Shop/Day clone item | stock/ID trùng | test transfer no-decay và unique IDs |
| Gather LIFO nhưng sort kho | rơi sai hàng | tách hold order và file output sort |
| Người 3/4 cùng sửa `step()` | merge conflict/logic lặp | helper + một owner wiring |
| Test cũ dùng kho đếm | fail đúng vì breaking | cập nhật fixtures có ghi lý do, không xóa test |

## 6. Quyết định cần nhóm xác nhận

- [ ] Field Item và chỗ lưu `next_item_id`.
- [ ] Một người sở hữu wiring xử lý tick trong `gather.py`/`quan.py`.
- [ ] Cấu trúc serializer/deserializer/validator dùng chung.
- [ ] P3-03 chốt `reserved` trước khi P3-04 consume.
- [ ] Chủ trách nhiệm merge/schema switch và tag.

**Ngày giờ/commit xác nhận:** _điền khi nhóm họp_  
**Quyết định thống nhất & reviewer:** _điền theo thực tế_  
**Kết quả smoke & proof:** _điền sau khi chạy_

## 7. Hậu quả và cách cập nhật tài liệu

- Bắt buộc ghi vào `CHANGELOG.md` việc v1.2 **không tương thích** với dữ liệu kho đếm và fixtures `reserved` dạng map trước đó.
- Cập nhật ví dụ inventory, scenario, event, README và mọi test sample sang IDs/fresh mới.
- Lưu `docs/proof/phase-3/` log của smoke thật + `docs/verification/phase-3.md` mapping test/AC.
- Nếu gặp sự cố tích hợp, giữ main/tag trước đó nguyên trạng; sửa trên nhánh tới khi v1.2 hoạt động. Không gắn tag với bản nửa v1.1 nửa v1.2.
