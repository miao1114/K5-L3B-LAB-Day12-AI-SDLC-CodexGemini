# CONTRACT P3-03 ↔ P3-04 — Quan Stock / Kitchen Freshness v1.2

> **Tính chất:** Hợp đồng phối hợp triển khai nội bộ. Các schema và luật được ghi rõ trong TICKET-03 là yêu cầu chính thức; tên hàm/helper minh họa **chưa được chốt** và phải đối chiếu source hiện tại. Mục đích: người 3 và người 4 cùng làm `quan.py` mà không ghi đè nhau.

## 1. Ranh giới trách nhiệm

| Công việc | P3-03 (người 3) | P3-04 (người 4) |
|---|---|---|
| Tạo/nhận kho cá thể | Chủ trì | Đọc đúng schema |
| Decay stock 0.25/s trong tick | Chủ trì | Dùng trạng thái sau decay |
| `spoiled` và re-reserve | Chủ trì | Không nấu ID đã spoiled |
| Chọn item tươi nhất/giữ ID | Chủ trì | Tiêu **chính các IDs** đã giữ |
| Lấy order reserved để nấu | Đồng thuận interface | Chủ trì |
| Tính `base_price` theo fresh | Không tự chốt giá ở lúc đặt món | Chủ trì tại `cook_started` |
| `cook_started.data.items` | Cung cấp item list | Chủ trì tạo event, sort kind/id |
| Chuyển order `reserved → assigned` | Đồng thuận source owner | Chủ trì hoặc helper đã thống nhất |
| Nấu/nhặt/serve/tip/paid | Không làm lại | Chủ trì |
| Khách rời/closing | Chủ trì lifecycle khách | Hỗ trợ hủy món trên stove/hand khi order rời |
| Snapshot khách + kho | Có trách nhiệm schema IDs | Xác minh payload stove/hand/base_price |

## 2. State schema bắt buộc

`quan.stock` (và `scenario.quan.stock`):

```json
[
  {"id":"I1","kind":"ca_loc","fresh":80},
  {"id":"I2","kind":"bong_sung","fresh":95}
]
```

`customers[].reserved` (cho order đang reserved):

```json
["I1"]
```

`customers[]` (minh họa fixture hợp lệ theo field contract):

```json
{
  "id": "C1",
  "table_id": "T1",
  "dish_id": "ca_loc_nuong_trui",
  "order_tick": 0,
  "state": "waiting",
  "patience_ticks_left": 3600,
  "order_status": "reserved",
  "reserved": ["I1"]
}
```

**Khác biệt:** Item object là thực thể vật lý trong stock; `reserved` chỉ là danh sách ID tham chiếu. Một ID không được bị hai đơn giữ. Khách có `reserved=[]` khi không giữ. Payload món tại stove/hand vẫn `{order_id,dish_id,base_price}` (giá chốt khi nấu).

## 3. Quy tắc mỗi tick bắt buộc

```text
Bắt đầu bước Quán
   ↓
Timer game + timer khách/bếp
   ↓
Giảm fresh tất cả nguyên liệu stock (gồm reserved)
   ↓
Event spoiled theo ID (chỉ khi vừa qua ngưỡng)
   ↓
Người 3: nhả toàn bộ reservation của đơn bị ảnh hưởng,
         re-reserve đúng 1 lần theo order_tick → table_id
   ↓
Chuyển bếp chín/cháy nếu cần
   ↓
Di chuyển + 1 cạnh interact E
   ↓
Người 4: chọn order reserved và nấu bằng IDs đang giữ,
         chốt base_price bằng fresh SAU DECAY
   ↓
Payment/closing/customer life cycle
   ↓
Khách mới (hoặc reservation extension nếu bật)
```

## 4. Giá và event

- Khi `cook_started`, lấy đúng các item ID từ `customers[].reserved`; đảm bảo `fresh >=30`, đủ recipe, không trùng và chưa tiêu.
- `base_price = floor(list_price * (sum(fresh)/number_of_items)/100)` **chỉ tính một lần**, ngay sau khi đã giảm độ tươi ở đầu tick.
- Sau khi gán `assigned`, IDs đã tiêu không còn trong stock và reserved list phải được giải phóng. Đừng giữ vật thể đã tiêu làm item stock.
- `cook_started.data.items` chứa **các object item đã tiêu** `{id,kind,fresh}`, sắp **kind rồi id**, không phải list ID hay map đếm.
- Khi phục vụ, `tip = floor(base_price * 0.2)` nếu còn >=50% patience; thanh toán cộng base_price+tip **một lần**.
- Khi khách rời khi món ở bếp/tay, dọn món theo `order_id`. Không hoàn nguyên liệu đã tiêu.

## 5. Ví dụ tính giá chính xác theo thứ tự tick

**Test A — 1 cá lóc fresh 100 tại tick 0**

- Input `interact:true` ở tick 0, player ở B1, order C1 có reserved `["I1"]`.
- Bắt đầu bước tick 1: item từ 100 → `100 - 1/240`.
- Giá `ca_loc_nuong_trui` (60) tại `cook_started` tick 1: `floor(60*(100-1/240)/100)` = **59** (nghìn đồng).
- Nếu dùng giá 60 vì đọc fresh của tick 0 là **sai thứ tự**.

**Test B — 2 bông súng tại thời điểm đã chốt cook**

- fresh chính xác tại tick nấu: 80 và 70.
- `mean_fresh=75`, giá `goi_bong_sung` niêm yết 40 → **30**.
- Nếu đây là giá trị của fixture tick 0 và nấu ở tick 1, cả hai phải hao tiếp trước khi nấu → giá có thể thấp hơn.

**Test C — qua ngưỡng lúc đang giữ**

- I1 fresh=30 tại tick 0, reserved vào đơn C1.
- Tick 1: I1 qua `<30`, phát spoiled(stock) trước re-reserve.
- Người 3 nhả toàn bộ reservation C1, thử một lần từ hàng còn tươi khác; nếu không đủ thì `unfulfillable`. Người 4 không được nấu I1.

## 6. API/hàm hỗ trợ (ĐỀ XUẤT, không phải contract chính thức)

Tùy code hiện tại, hai bên có thể chốt các hàm nhỏ:

```python
# Tên chữ ký chỉ minh họa, điều chỉnh theo source hiện tại.
# Được gọi TRƯỚC kitchen interaction:
expire_stock_and_retry_reservations(state, tuning, tick, emit)

# Chọn order + lấy đúng item vật lý đã reserved:
resolve_reserved_items_for_order(state, order_id) -> list[Item]

# Khi nấu thì ghi nhận đã tiêu và chuyển trạng thái:
consume_reserved_items(state, order_id, item_ids)
```

Không tạo API mới nếu source đã có chức năng tương đương. Không gọi helper decay **lần thứ hai** trong tick.

## 7. Tránh conflict Git

1. Người 3 sửa phần decay/re-reserve/stock; người 4 chỉ sửa phần start cooking/price/event/serve/payment, hoặc tách helper nhỏ.
2. Nếu cả hai cần sửa chung `step()`: chốt điểm hook trước, chỉ một người thực hiện wiring cuối, người còn lại cung cấp helper/tests.
3. Mỗi người có test độc lập; sau khi merge phải chạy case tick1 và re-reserve + cook.
4. Bất kỳ thay đổi schema/helper nào cũng ghi thông báo vào notes/PR trước khi merge.

## 8. Checklist review chung

- [ ] `stock` là mảng item; reserved là list IDs; không còn logic đếm cũ trên code path v1.2.
- [ ] Không double-decay hoặc double-consume.
- [ ] Spoiled trước re-reserve; re-reserve trước cook.
- [ ] Chốt giá theo item **sau decay**, không theo list price gốc.
- [ ] `cook_started.data.items` đúng object/sort.
- [ ] Không nhầm đơn, không double-paid, không đổi price sau cook.
- [ ] Regression 2 bếp/4 bàn và day còn chạy.
- [ ] Interface được người 3 và người 4 xác nhận.
