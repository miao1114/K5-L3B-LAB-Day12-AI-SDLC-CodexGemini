# NPC Walk-In → Seating → Eating → Walk-Out

Status: **COMPLETE** trong phạm vi frontend. Đã đọc toàn bộ
`docs/prompts/NPC-WalkIn-Seating-Codex.md`, kiểm tra `AGENTS.md`, `drawQuan`,
RAF/poll/pause/projection và snapshot/backend Quán trước khi sửa.
Nhánh làm việc: `updatelevel`; không merge, push, tag hoặc tạo release.

## File và assets

- `chonoi/web/index.html`: `NpcWalkController`, cache theo customer ID,
  reconcile membership snapshot, renderer spritesheet, depth sorting và visual clock RAF.
- `tools/verify_npc_walk.py`: kiểm tra controller và integration Canvas bằng Chrome,
  dùng snapshot fixtures dựa trên snapshot thực từ `LiveGame`.
- `CREDITS.md`: ghi nhận spritesheet do nhóm cung cấp.
- `docs/proof/npc-walk/`: báo cáo JSON và ba ảnh chụp Chrome thực tế.
- Bốn WebP mới có sẵn trong working tree, được dùng trực tiếp:
  `khach-{nam,nu}-di-bo.webp` và `khach-{nam,nu}-ngoi.webp`.
  Hai PNG `nhanvatnamngoian.png`, `nhanvatnungoian.png` không dùng/sửa.
  Giữ nguyên sprite khách cũ làm fallback, Bà Út và tất cả bàn/bếp/background.

Walking: 5 cột × 3 hàng, cell 260×404; hàng 0 xuống, 1 lên, 2 ngang phải,
mirror cho trái. Cột 0 đứng, 1–4 bước ở 9 FPS. Sitting: 4 cột × 1 hàng,
cột 0 chờ, 1 chào (chưa dùng), 2 ăn, 3 uống. Crop theo kích thước ảnh thực
`naturalWidth/columns`, `naturalHeight/rows`, vì chiều cao ảnh ngồi thực tế
không nhất thiết bằng 471 px như bảng prompt (nam là 450 px).
Không cần đổi server: route WebP hiện có phục vụ đủ bốn file.

## Đường đi và lớp hiển thị

Đã xem `quan-nen.webp` và cả bốn ảnh `ban-mot/hai/ba/bon.webp`.
Cửa có thật ở giữa mép dưới background, phía cầu gỗ; ghế sau nằm phía trên bàn.
Controller đọc `tables[].pos` và bounds thực từ snapshot, sau đó dùng cùng
`at(worldPosition)` của renderer; resize không lưu lại pixel cũ.

Với bounds hiện tại x=[0,16], z=[0,10]:

- Cửa `(8.96, -0.8)`, chiếu lên khoảng `(0.50w, 0.94h)`.
- Waypoint sát cửa `(6.56, 0.2)`, trục đi chung x=6.56 ở phía trái khu bàn.
- Nhánh từng bàn: `(6.56, table.z+2.3)` → `(table.x-0.6, table.z+2.3)`
  → ghế `(table.x-0.6, table.z+1.65)`.
- T1 [9,2] → ghế [8.4,3.65]; T2 [13,2] → [12.4,3.65];
  T3 [9,6] → [8.4,7.65]; T4 [13,6] → [12.4,7.65].

Offsets được scale theo bounds nếu kích thước world thay đổi.
Thời lượng đi được kẹp 0.8–2.2 giây, chuyển ngồi/đứng 220 ms.
Lúc rời đi dùng đường đảo ngược; nếu chưa tới bàn chỉ đảo phần đã đi,
không nhảy tới ghế rồi mới ra. Nhân vật và bàn được sắp theo chân/y;
bàn vẽ đúng một lần, che thân dưới NPC ngồi, vẫn thấy tay và động tác ăn/uống.
Thanh xanh/vàng/đỏ đi theo đầu NPC; nhãn bàn, reservation, badge món trên tay
và HUD/high contrast giữ nguyên.

## Đồng bộ và giới hạn gameplay

- ID mới trong phiên đang chạy: entering → sitting → waiting/eating.
- Snapshot đầu khi refresh: order cũ hydrate thẳng vào ghế; order vừa tạo
  trong 60 phase ticks gần nhất vẫn đi vào từ cửa, đối chiếu `order_tick`
  với `phase_tick` (không dùng tick tổng của Day). Khách được phục vụ sớm
  khi đang entering được đưa tới ghế an toàn, không trì hoãn phục vụ.
- Khách mất khỏi snapshot sau paid/customer_left/reservation failure:
  leaving đúng một lần, giữ bản sao visual tới cửa rồi xóa. Không đọc lại
  event window để tránh trả tiền/rời bàn trùng. Bàn thuộc khách mới ngay lập tức.
- Token theo ngày/màn, tick quay lại và restart xóa cache; Shop/DayResult không
  giữ ghost. Request epoch của pause không được dùng làm session identity.
- Visual delta từ RAF, kẹp 50 ms/frame; pause/ẩn tab/lỗi đóng băng và bỏ delta
  treo khi resume. Quan độc lập tiếp tục redraw khi NPC đang động, kể cả lúc
  shift finished để hoàn tất walk-out. Reduced motion mặc định hiển thị tĩnh tại bàn.
- Checkbox **Khách đi bộ** dưới khung chơi cho phép bật/tắt riêng hoạt ảnh NPC,
  lưu `chonoi.npcMotion` trong localStorage. Mặc định theo reduced-motion của hệ
  thống; lựa chọn rõ ràng của người dùng được ưu tiên. Không đổi hoạt ảnh/HUD khác.
  Checkbox được đồng bộ cả khi nhận snapshot và khi media preference thay đổi.
- Lỗi/chưa tải sheet dùng khách cũ; lỗi tải ghi cảnh báo developer, không crash.

Không sửa Python simulation, contract, RNG, thời gian khách, order, tiền/tip,
uy tín, phân bàn, schema snapshot/JSONL hoặc headless. Visual không giữ bàn
và không gửi thao tác simulation để tạo/di chuyển NPC.

## Kiểm chứng thực tế

Lệnh trên Windows:

```powershell
.venv/Scripts/python.exe tools/verify_npc_walk.py
$env:PYTHONPATH='tests;.'; $env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m unittest test_live -v
```

- Chrome thật: **32/32 checks PASS**, không có JavaScript exception.
  Xem `docs/proof/npc-walk/verification.json` cho từng check.
- `test_live`: **3 tests, OK** (snapshot không đổi simulation, assets,
  state/input/clean stop).
- Đã kiểm tra T1–T4, hai giới, đồng thời tới, hydrate, ID/ngày, table reuse,
  rời sớm, cache exit một lần, phục vụ khi đang vào, pause/resume,
  Quan độc lập không poll, Day/Shop, finished shift, fallback, restart và resize.
- Ăn/uống: quan sát drawImage crop thực có cả cột 2 và 3.
- Ảnh thật: `seated-four-tables.png`, `eating-and-status.png`, `walking-out.png`.
  Bổ sung `real-arrival-door.png` và `real-arrival-walking.png` từ simulation
  thật với kho cá lóc, khách sinh theo tuning chính thức và poll `/state` thật,
  không route/mocking response. Đã xác minh entering → đổi vị trí → waiting.
  Browser chạy viewport 1280×720, full-page screenshot có thể cao hơn viewport;
  kiểm tra resize thêm 960×720. Sau lần đầu đã điều chỉnh ghế vì bàn che tay,
  xác minh lại và lưu ảnh/báo cáo của bản cuối.
- Không chạy benchmark, soak hoặc regression toàn bộ không liên quan.

## Giới hạn còn lại / chạy local

- Browser dùng fixtures để chủ động bao phủ các cạnh và một ca kiểm tra sinh khách
  từ simulation thật. Chưa chơi tay hết nhiều ngày; không tuyên bố đã chạy
  soak/headless toàn bộ.
- Nếu backend đóng ca và chuyển DayResult ngay, cache bị xóa theo màn;
  animation không trì hoãn vòng ngày để chờ khách đi hết.
- Sheet là các pose rời; chuyển ngồi/đứng dùng crossfade, ăn/uống đổi pose
  và nhún nhẹ, không phải skeleton animation. Cột chào chưa sử dụng.
- Metadata `docs/npc-sprite-map.json` không có trong workspace khi làm task;
  dùng mapping và kích thước thực của bốn ảnh, không tự tạo schema khác.

Chạy `.venv/Scripts/python.exe -m chonoi.live --mode quan`, mở URL được in ra.
Vòng ngày dùng launcher hiện có của nhóm; controller tự hoạt động khi screen=quan.
Nếu tab đang mở từ trước khi sửa, tải lại bằng Ctrl+F5. Ở `localhost:8783` đã
đối chiếu HTML server trả về trùng file workspace; không restart hoặc thay đổi
phiên chơi hiện có của người dùng. Bật **Khách đi bộ** dưới khung chơi nếu muốn
ưu tiên hoạt ảnh dù hệ thống đang yêu cầu giảm chuyển động. Khách cũ đã ngồi
không bị buộc ra cửa đi lại; quan sát khách mới đến.

Commit đề xuất: `feat(ui): animate restaurant NPC arrival, seating, eating and departure`.

## Regression khi sửa animation Bà Út

Đã chạy lại `tools/verify_npc_walk.py`: **32/32 PASS** sau thay đổi nhịp
sprite của nhân vật chính. `tools/verify_player_animation.py`: **15/15 PASS**,
có ca simulation thật xác minh Bà Út đi bộ và khách đi vào đồng thời.
Chi tiết: `docs/notes/Player-Animation.md`. Hai bộ điều khiển hoạt ảnh độc lập.
