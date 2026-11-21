# Fish Stack, Auto End Quán và tiến trình 5 ngày

> Cập nhật tiếp theo: menu/spawn đã mở khóa dần 2→6 món; kế hoạch web hiện dùng
> 3/5/7/9/12 ô. Xem `Menu-Unlock-Resource-Spawn.md`; bảng plan/proof bên dưới
> lưu lịch sử của lượt triển khai stack/Auto End trước khi có unlock.

Trạng thái: **COMPLETE** trong phạm vi gameplay mở rộng web local.
Nhánh `FRESHNESSPRICING`, baseline `7b59871`; chưa stage/commit/push.

## Audit trước triển khai

- Working tree có sửa UI/nhiệm vụ từ lượt trước và các thay đổi riêng của người dùng;
  không reset, merge, ghi đè các thay đổi đó hoặc sửa tag/release.
- Contract hiện có là v1.2. Đối chiếu AGENTS, manifest, TICKET-03 v1.2,
  TICKET-02 v1.1 và các module Gather/Quán/Kitchen/Day/inventory/day_config/web.
  Repo không có nguồn v1.3 để xác minh riêng; không tuyên bố đã kiểm chứng v1.3.
- Gather chuẩn dùng `len(hold)` để tính sức chứa. Một đàn linh sinh 3 item độc lập
  `{id,kind,fresh}` và chiếm 3 ô. Mất hàng chuẩn tính trên cá thể và bỏ LIFO.
- Quán chuẩn có lượt khách đầu tick 120, sau đó mỗi 900 tick; chỉ tạo đơn có đủ
  nguyên liệu chưa giữ và còn tươi trong menu hợp lệ, một bàn cho một khách.
  Chỉ đóng ca khi hết thời gian. Kitchen đã xử lý nấu/ready/hand/serve/paid đúng;
  giữ nguyên consumer `RestaurantStock.consume`, không tiêu kho hai lần.
- DaySim/Shop thật đã có trong backend, nhưng adapter real-scenes cũ chỉ gọi hai
  engine riêng, điều phối màn hình bằng preview, chưa nối Shop và thống kê thu thập.
- Nhiệm vụ HUD đang chạy: đọc `day_plan.ingredients`/`hold` thật. Tái sử dụng,
  không viết lại hoặc thay bộ đếm giả. Plan web trước đây giảm một suất mỗi món,
  chưa tăng tổng số suất qua từng ngày.

## Cô lập khỏi Test Contract

`chonoi.interactive` cung cấp subclass `InteractiveGather`, `InteractiveQuan`,
`InteractiveDaySim`, `InteractiveSession`. Chỉ CLI web `--real-scenes` mặc định
chọn đường chạy này. Headless, runner chuẩn, Session chuẩn, preset contract và
schema kho không đổi; không bật extensions bằng cách sửa contract chung.

`--contract-plan` chọn adapter preview cũ và mục tiêu chính thức, không dùng luật
stack/đóng sớm. Adapter cũ vẫn có giới hạn Shop như trước. Đây không phải thay thế
cho kiểm chứng chuẩn: chế độ chấm vẫn là `chonoi.headless`.

File Gather chung chỉ thêm ba hook: tính số ô cần, ghi nhận item vừa thu và xử lý
quái. Nhánh mặc định giữ nguyên luật cá thể; phần xử lý quái được tách ra helper
với cùng thứ tự và payload. Cần sửa file chung để tái sử dụng bắt/hái/sinh tồn,
tránh sao chép cả vòng tick. Regression chuẩn đã chạy thực tế.

## Fish Stack

- `hold_items` luôn giữ cá thể thật với ID và độ tươi riêng. `slots` là danh sách
  các nhóm ID ngoài schema kho; chỉ một lần bắt **cá linh** mới tạo nhóm chung.
- Mỗi đàn tạo nhóm riêng; hai đàn → 6 item, 2 ô. Các loại khác vẫn từng item/ô.
  Giỏ còn 1 ô nhận được đàn linh, 12 ô thì từ chối nguyên đàn.
- Item có sẵn trong scenario không có lịch sử bắt: giữ từng ô riêng, không tự gộp.
- Monster dùng thuật toán chung trên danh sách ô. Mất `floor(ô × loss_ratio)` ô
  cuối; mỗi ô mất toàn bộ ID thành viên, item trong nhóm cũng liệt kê ngược LIFO.
  Ngất xóa hết. Chế độ chuẩn vẫn mất theo cá thể.
- Freshness chạy trên từng cá thể. Một item ươn không xóa stack/giải phóng ô;
  item ươn không được dùng nấu. Kho bàn giao là mảng cá thể nguyên vẹn, không kèm
  quantity/stack_id. Recipe dùng 3 linh tiêu đúng 3 ID; recipe dùng 2 giữ item thứ ba.
- Snapshot web thêm `hold_slots` và `hold_slots_used`; UI vẽ từng ô với `×3`,
  hiển thị số ô và số nguyên liệu riêng. HUD freshness/nhiệm vụ vẫn đếm `hold` thật.

## Auto End và lượt khách

`InteractiveQuan._settle_customers` chạy settlement chuẩn trước, rồi kiểm tra:

1. Có khách eating chưa thanh toán → còn việc.
2. Có món cooking/ready hoặc trên tay → còn việc (ownership/timer do Kitchen quản lý).
3. Có reserved hợp lệ, đủ recipe, còn tươi, không trùng claim khác → còn việc.
4. Có thể reserve ít nhất một recipe thuộc menu ngày từ kho chưa giữ → còn việc.

Nếu không còn việc, đóng các đơn bất khả thi bằng cleanup `closing` sẵn có:
không phạt uy tín vì đóng ca, không hoàn kho đã tiêu, không tạo payment giả;
đánh dấu `done` và phát một `quan_end` nội bộ với reason `inventory_exhausted`.
Không xóa kho dư, không ép đồng hồ về 0, không đổi reason chuẩn của headless.

**Ca bắt buộc 1 bông súng, 0 cá lóc:** Day 1 không có recipe nào đủ. Tick đầu
đóng ca, không tạo khách, giữ bông súng trong kho/remaining, tiền và uy tín không đổi.
UI có thông báo hết khả năng chế biến, DayResult → Shop thật. Ngày chỉ hoàn thành
sau `shop_done` hoặc hết timer Shop; nâng cấp dùng luật `_buy` của DaySim.

Nhịp khách web là 5 giây trong `chonoi/web/gameplay.json`; lượt đầu vẫn theo
contract (2 giây). Tái sử dụng scheduler hiện có, chỉ đổi tuning riêng của instance
web. Không tạo khách mỗi frame; không trùng bàn/claim; số suất mục tiêu không phải
trần số khách. Headless vẫn 15 giây/lượt. Kho có hàng ngoài menu hoặc chỉ hàng ươn
không giữ ca mở vô hạn.

## Thống kê và Shop

`InteractiveDaySim.step` thu event đúng một lần: fish_caught đếm yield và số đàn,
gather đếm rau, cook_started đếm item tiêu, served/customer_left/paid đếm dịch vụ,
tiền và boa. Không đọc lại event window để cộng dồn. Snapshot/render/pause không
cộng số. Capture `brought` trước đổi Gather → Quán; capture `remaining`, `spoiled`,
money/reputation/reason trước đổi Quán → Shop. Mỗi ngày giữ kết quả riêng; reset
thống kê vào `_start_day`, giữ economy/upgrades/ID registry theo DaySim.

DayResult phân biệt cá đã bắt (con/đàn), rau đã hái, mang về, đã nấu, tồn và ươn.
Doanh thu/earned theo luật gồm tiền món + boa; boa được liệt kê riêng, không cộng
lần nữa vào tiền. Summary cộng kết quả các ngày; `remaining` trong Summary là
tổng tồn cuối các ca (hàng dư vẫn bỏ sau Shop theo DaySim), không phải kho đang mang.

Web dùng `InteractiveDayWeb` bọc Session/DaySim, có các màn intro/result để người
chơi xác nhận. Timer gameplay do tick backend chạy; frontend chỉ gửi input/action.
Shop thật hỗ trợ mua cấp kế tiếp, phản hồi thiếu tiền, timeout, pause và ngày tiếp.

## Kế hoạch 5 ngày và tính khả thi

Nguồn: `chonoi/web/day-plan.json`; ingredients luôn do `day_plans` tính từ recipe.
Sáu recipe lõi không sửa. Giữ bông súng ở 2, tăng dần suất và đa dạng món.

| Ngày | Suất | Loại món | Mục tiêu nguyên liệu | Ô cần |
|---|---:|---:|---|---:|
| 1 | 2 | 2 | lóc 1, bông súng 2 | 3 |
| 2 | 3 | 2 | lóc 2, bông súng 2 | 4 |
| 3 | 4 | 3 | lóc 2, linh 3, bông điên điển 1, bông súng 2 | 6 |
| 4 | 5 | 4 | lóc 2, linh 6, bông điên điển 3, bông súng 2 | 9 |
| 5 | 6 | 5 | lóc 2, linh 6, kèo 2, bông điên điển 3, bông súng 2 | 11 |

Không dùng máy móc 6→10 suất vì giỏ, thời gian và việc hái cây cần mọc lại. Lần
kiểm chứng đầu với 3 cá lóc/ngày cho thấy bot không hoàn thành Day 4; đã điều chỉnh
menu sang tăng lẩu dùng linh theo stack, đồng thời bot nổi lên trước hành trình dài
và tránh cá sấu. Đây là sửa thiết kế/đường điều khiển, không nới timer, RNG, hit
hoặc freshness để che lỗi. Không dùng kết quả thử thất bại làm bằng chứng PASS.

Verifier cuối dùng seed 1, spawn mặc định, di chuyển thật, oxy/hao tươi/quái hoạt động,
không teleport/cấp hàng. Thu đủ mục tiêu lần lượt **18.25 / 41.78 / 27.55 / 35.73 /
44.13 giây**, dùng **3/4/6/9/11 ô**. Mua HP/oxy thật từ tiền kiếm qua Shop; bán
thành công **2/3/4/5/6 món**, không khách bỏ đi. Hoàn tất 5 Shop sau 25.160 tick.
Replay cùng input cho event và summary giống nhau. Đây là bằng chứng tồn tại
đường chơi khả thi, không đảm bảo mọi seed/chiến thuật đều thắng.

## AC01–AC22

| AC | Trạng thái | Bằng chứng |
|---|---|---|
| 01 | PASS | Mỗi đàn sinh 3 item, ID duy nhất |
| 02 | PASS | Một đàn/ô, kể cả ô cuối |
| 03 | PASS | Chrome hiển thị ×3 |
| 04 | PASS | Hai đàn = 6 item/2 ô |
| 05 | PASS | Handoff đủ 3 cá thể |
| 06 | PASS | ID/fresh giữ qua handoff; mixed fresh test |
| 07 | PASS | Standard capacity/regression giữ nguyên |
| 08 | PASS | Kho đủ recipe hoặc reserved giữ ca mở |
| 09 | PASS | Scheduler web tiếp tục có lượt khi đủ điều kiện |
| 10 | PASS | Không trùng table hoặc claim ID |
| 11 | PASS | Hai bếp cooking không đóng |
| 12 | PASS | Ready và hand độc lập không đóng |
| 13 | PASS | Chờ eating, paid 70/boa 11 một lần, uy tín 3.2 |
| 14 | PASS | Kho lẻ/ươn/ngoài menu đóng đúng, không xóa hàng |
| 15 | PASS | DayResult → mua Shop thật → Day 2; hết 5 Shop → Summary |
| 16 | PASS | D1 2 suất, 3 ô, hai món đơn giản |
| 17 | PASS | Tăng nguyên liệu/đa dạng, M2 ngày 3 theo DaySim thật |
| 18 | PASS | 2→3→4→5→6 suất |
| 19 | PASS | ingredients tính từ recipe, kiểm từng ngày |
| 20 | PASS | HUD nhiệm vụ hiện đúng ngày khi chạy đủ 5 ngày trên Chrome |
| 21 | PASS | Thu đủ 5 mục tiêu bằng movement thật <180 giây, đủ ô |
| 22 | PASS | Lớp chuẩn không chọn extension; regression CLI/JSONL/Day |

## Test thực tế

Môi trường Python 3.14 trong `.venv`, Playwright + Chrome, Windows.

```powershell
$env:PATH = (Join-Path $PWD '.venv\Scripts') + ';' + $env:PATH
$env:PYTHONPATH = 'tests;.'
$env:PYTHONUTF8 = '1'
python3 -m unittest discover -s tests -v
python3 -m unittest test_interactive_gameplay -v
python3 tools/verify_interactive_progression.py
python3 tools/verify_interactive_browser.py
```

- **PASS:** full regression **239 tests, 72.908 giây**, 0 fail/error.
- Sau bổ sung hai ca độc lập hand/mixed freshness: **18 tests interactive, 0.095
  giây**, 0 fail/error. Không tuyên bố đã chạy lại full suite 241 sau khi thêm hai test.
- **PASS:** 5 ngày movement thật + deterministic replay, 25.160 tick.
- **PASS:** Chrome 1280×720, bắt hai đàn qua Space và HTTP thật, 2 ô/6 item;
  DayResult đếm 6 con/2 đàn; Shop mua oxy thật và giỏ ngày sau rỗng.
- **PASS:** Chrome ca 1 bông súng đóng ngay, còn dư 1, không payment giả.
- **PASS:** browser chạy đủ các màn 5 ngày bằng replay input đã kiểm chứng;
  intro/result/mua Shop/đóng Shop qua nút HTTP thật; results trùng báo cáo backend.
  Không pageerror/console error. Fixture vị trí/cá dùng riêng để kiểm UI stack;
  replay 5 ngày không bỏ qua scene hoặc cấp dữ liệu kết quả giả.
- `test_web_progression_preserves_recipes_and_standard_contract` thay kỳ vọng web
  một suất/món cũ vì yêu cầu progression mới; không thay test chuẩn để làm xanh.

Các ca Auto End người dùng bổ sung đều có test: kho lẻ, kho đủ recipe, kho khả dụng
0 do reserved, hai bếp cooking, ready, hand riêng, eating/pay, kho ươn và chỉ end một
lần. Có thêm kiểm ngoài menu và reserved vừa ươn.

Bằng chứng mới riêng tại [gameplay-enhancement](../proof/gameplay-enhancement/):
`regression-tests.txt`, `interactive-tests.txt`, `progression-report.json`,
`progression-events.jsonl`, `progression-inputs.json`, `browser-report.json`;
ảnh `fish-stacks-1280x720.png`, `one-flower-auto-end.png`, `real-shop.png`,
`replay-day1-result.png` đến `replay-day5-result.png`, `five-day-summary.png`.
Không ghi đè bằng chứng Phase 1–4.

## File sửa/thêm và rủi ro còn lại

- `chonoi/sim/gather.py`: hook mặc định giữ hành vi chuẩn.
- `chonoi/interactive.py`, `chonoi/interactive_web.py`: luật và adapter web riêng,
  tái sử dụng engine, scheduler, Kitchen và DaySim/Shop hiện có.
- `chonoi/web/day-plan.json`, `chonoi/web/gameplay.json`: progression/nhịp khách web.
- `chonoi/web/index.html`: số ô/stack và DayResult/Shop; không viết lại daily quest.
- `docs/proof/phase-2/day_fixture.py`: chọn adapter mở rộng, giữ adapter cũ;
  server dùng chung cho kiểm thử, không thêm endpoint debug.
- `tests/test_interactive_gameplay.py`, `tests/test_phase2_live_preview.py`;
  `tools/verify_interactive_progression.py`, `tools/verify_interactive_browser.py`;
  README, notes này và proof riêng.

Không có chức năng bắt buộc còn bỏ dở trong phạm vi này. Giới hạn: chưa benchmark
FPS/mobile; tính khả thi mới chứng minh seed 1, không khảo sát mọi seed. Recipe
ngẫu nhiên có thể bán lệch cơ cấu dự kiến, không giới hạn số khách theo số suất.
Nếu sau này owner thay lifecycle/tick của DaySim hoặc Kitchen cần chạy lại test
subclass. Không sửa `docs/contracts/`, manifest hay bằng chứng nhóm có sẵn.

## Chạy web, Git và PR đề xuất

```powershell
.venv\Scripts\python.exe docs/proof/phase-2/day_fixture.py --real-scenes --days 5 --port 8783
```

Mở http://127.0.0.1:8783/ → Chơi → Ra bến. WASD, Space bắt cá, E hái/cập bến/bếp/bàn;
P/Esc pause. DayResult → Ghé cửa hàng → mua hoặc Rời cửa hàng.

Git vẫn ở FRESHNESSPRICING; file task chưa stage/commit. TEAM, manifest, spec bị
xóa và verification vốn có thay đổi từ trước được giữ nguyên, không đưa vào commit
task theo kiểu `git add .`. Commit đề xuất:
`feat(web): thêm stack cá linh, đóng Quán khi hết món và tiến trình 5 ngày`.

Mô tả PR đề xuất:

> Bản chơi web nay nhóm mỗi đàn cá linh thành một ô nhưng vẫn giữ đủ cá thể/độ tươi
> để nấu. Quán đóng sớm khi không còn recipe hay hoạt động phục vụ có thể hoàn thành,
> kể cả kho còn hàng lẻ; chờ món/khách đang xử lý và thanh toán đúng một lần.
> DayResult thống kê thu thập, hàng mang về, đã nấu và còn dư; nối Shop thật với
> DaySim, kế hoạch tăng 2→6 suất trong 5 ngày. Luật mở rộng tách khỏi headless chuẩn.
>
> Kiểm chứng: 239 regression + 18 test interactive ở lượt kiểm cuối; replay seed 1
> thu đủ/bán qua 5 ngày deterministic; Chrome 1280×720 kiểm stack, ca một bông súng,
> Shop và đủ màn 5 ngày, không lỗi console. Proof và giới hạn tại notes này.
