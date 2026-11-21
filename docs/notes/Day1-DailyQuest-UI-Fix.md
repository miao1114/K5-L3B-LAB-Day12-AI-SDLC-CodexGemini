# Day 1 — Daily Quest UI Fix

> Cập nhật tiếp theo: Fish Stack/Auto End đã nối Shop thật và thay kế hoạch web bằng
> progression 2→6 suất. Xem `Fish-Stack-Auto-End-Day-Progression.md` để biết trạng thái
> hiện tại; phần giới hạn Shop và kế hoạch cũ bên dưới là lịch sử kiểm chứng trước đó.

Trạng thái: **PASS** trong phạm vi HUD nhiệm vụ và adapter web hiện có.
Nhánh: `FRESHNESSPRICING`, baseline `7b59871`. Chưa commit/push thay đổi này.

## Điều chỉnh độ khó theo yêu cầu tiếp theo

Người chơi yêu cầu giảm nhiệm vụ vì bông súng khó thu đủ. CLI web real-scenes
hiện mặc định nạp `chonoi/web/day-plan.json`, một suất mỗi món mỗi ngày.
Đây là cấu hình chơi web riêng; preset `game.contract.json`, DaySim/headless,
công thức và luật thu thập không đổi. `--contract-plan` khôi phục mục tiêu chính thức;
`--scenario` tường minh có ưu tiên cao hơn cấu hình mặc định.

| Ngày | Mục tiêu bản web nhẹ hơn |
|---|---|
| 1 | Cá lóc 1, bông súng 2 |
| 2 | Cá lóc 1, cá linh 3, bông điên điển 1 |
| 3 | Bông súng 2, cá lóc 1, bông điên điển 1, cá kèo 2 |
| 4 | Cá linh 2, cá kèo 1, kèo nèo 1, bông điên điển 1, cá lóc 1, bông súng 2 |
| 5 | Cá linh 5, cá kèo 1, kèo nèo 1, bông điên điển 2, cá lóc 1 |

Ngày 5 vốn đã một suất mỗi món nên giữ nguyên mức tối thiểu theo menu đó.
Backend tính lại ingredients từ recipe; không hard-code số đếm trong frontend.
Các ảnh/log 222 test bên dưới thuộc lần kiểm chứng mục tiêu chính thức trước đó.

**PASS:** kiểm chứng sau giảm độ khó: 18 test adapter/Day Loop, 5.029 giây,
0 fail/error; log `docs/proof/daily-quest/easier-plan-tests.txt`.
Chrome chạy đúng CLI localhost:8783 xác nhận Ngày 1 cá lóc 0/1 và bông súng 0/2,
không pageerror; ảnh `docs/proof/daily-quest/day1-easier-1280x720.png`,
snapshot `docs/proof/daily-quest/easier-plan-state.json`.
Đã khởi động lại demo (PID 9732) và tạm dừng sau kiểm chứng để người chơi tiếp tục.

## Audit và nguyên nhân

- **PASS**: kiểm tra Git, AGENTS, README, manifest; đối chiếu TICKET-03 v1.2
  với luật kế thừa TICKET-02 v1.1. Không sửa contract/schema hay luật simulation.
- Backend `DaySim.snapshot()` đã có `day_plan`, được tính bằng `day_config.day_plans`;
  Gather xuất `hold` cá thể thật. Không cần viết lại Day Loop.
- Web đang chạy qua `docs/proof/phase-2/day_fixture.py --real-scenes`, không phải
  `DaySim`: adapter dùng các engine Gather/Quán thật và điều phối màn hình preview.
  Trước sửa, `/state` không trả day_plan/needed trong nhánh real-scenes;
  DayIntro liệt kê cả sáu món và bỏ phần nguyên liệu nếu live_scenes=true.
- UI chỉ có dòng `goal-line` trong giỏ, phụ thuộc `day.needed` không được adapter gửi.
  Dòng cũ đếm cả hàng ươn. Không có điều kiện ẩn nhiệm vụ riêng Day 1/Day 2;
  điều kiện Day >= 3 tìm thấy thuộc việc vẽ cá sấu, không phải nhiệm vụ.

## Thay đổi

| File | Nội dung |
|---|---|
| `chonoi/web/index.html` | Bảng nhiệm vụ bên trái, icon sẵn có, số lượng/progress/tick, tổng giữ và số ươn; DayIntro hiện nguyên liệu |
| `docs/proof/phase-2/day_fixture.py` | Dùng chung day_plans với backend thật; gửi kế hoạch ở mọi màn hình; menu/số suất và Quán theo ngày; nhận scenario qua bộ đọc chuẩn; tách hàm tạo HTTP server để kiểm thử cùng endpoint thật |
| `tests/test_phase2_live_preview.py` | So Day 1–5 với DaySim, menu và giỏ mới, scenario tùy chỉnh và giữ dữ liệu qua Start/DayIntro/Gather |
| `tools/verify_daily_quest_browser.py` | Kiểm chứng Chrome với HTTP adapter thật, phím Space/E, ảnh 1280×720 và console |
| `README.md` | Lệnh chạy web và kiểm chứng, ghi rõ giới hạn Shop |
| `docs/proof/daily-quest/` | Log regression, báo cáo browser, ảnh Day 1–5 |

Phải sửa file web dùng chung vì HUD hiện tại thiếu UI; phải sửa adapter preview vì
đây là server web người chơi đang dùng và thiếu mapping dữ liệu. Không sửa
`DaySim`, Gather, Quán, kho, RNG, timer, công thức, sức chứa hay JSONL headless.
Các thay đổi có sẵn của người dùng ở TEAM/manifest/spec/verification giữ nguyên.

## Logic tiến độ

Nguồn mục tiêu: `day_plan.ingredients` từ backend; tương thích `needed` của fixture cũ.
Mỗi snapshot đếm lại cá thể trong `hold` theo kind. Tiến độ là số có fresh >=
`meta.spoil_threshold` do server lấy từ tuning.inventory (preset hiện tại: 30).
Hiện tổng giữ và số fresh dưới ngưỡng riêng; không xóa hàng ươn. Không giữ bộ đếm
thu thập cộng dồn. Khi mất hàng, ngất hoặc hao tươi, snapshot tiếp theo giảm tiến độ.
Nếu thiếu độ tươi/ngưỡng của cá thể v1.2, không đoán rằng cá thể còn dùng được.

Đủ mọi mục tiêu thì hiện tick và lời nhắn hoàn thành. `setText` chỉ thay live region
khi nội dung thay đổi, tránh lặp thông báo mỗi frame. Mất điều kiện sẽ bỏ hoàn thành.
Không có hành động trả thưởng hoặc chuyển pha. Gather độc lập không có kế hoạch
hiện “Chế độ thu thập tự do”.

## Kiểm chứng thực tế

Windows, Python 3.14 trong `.venv`; PATH thêm `.venv/Scripts`, `PYTHONPATH=tests;.`,
`PYTHONUTF8=1`. Cài Playwright trong venv để chạy Chrome đã có trên máy.

```powershell
$env:PATH = (Join-Path $PWD '.venv\Scripts') + ';' + $env:PATH
$env:PYTHONPATH = 'tests;.'
$env:PYTHONUTF8 = '1'
python3 -m unittest discover -s tests -v
.venv\Scripts\python.exe tools/verify_daily_quest_browser.py
```

- **PASS**: toàn suite **222 tests**, 34.369 giây, 0 fail/error.
  Log: [regression-tests.txt](../proof/daily-quest/regression-tests.txt).
  Bao gồm regression Day Loop, headless/CLI/scenario/JSONL, monster, faint,
  vật phẩm/độ tươi và bếp; hai test mới nằm trong suite này.
- **PASS**: Chrome localhost qua `/state`, `/action`, `/input`, viewport 1280×720;
  không pageerror/console error. [browser-report.json](../proof/daily-quest/browser-report.json).
- **PASS**: Day 1 mặc định cá lóc 0/3, bông súng 0/6; phím Space bắt cá thành 1/3,
  phím E hái cây thành 1/6 bằng engine thật.
- **PASS**: giỏ scenario sẵn 3 cá lóc/5 bông súng, E hái nốt → hai dấu tick,
  thông báo chỉ thay một lần; tiếp tục Gather, tiền vẫn 0. Bỏ một cá thể khỏi
  fixture giỏ → tiến độ giảm và trạng thái hoàn thành bị gỡ.
- **PASS**: scenario đổi Day 1 thành 1 cá lóc; giỏ có fresh 30 và 29.99:
  tick 0 hiển thị 1/1, tổng 2/ươn 1; sau hao tươi thật hiển thị 0/1,
  tổng 2/ươn 2, cả hai cá thể vẫn trong giỏ.
- **PASS**: Day 2–5 tự đổi mục tiêu lấy từ backend, giỏ mới không giữ tiến độ cũ;
  đàn cá linh thực làm tăng đúng 3. Unit test đối chiếu từng kế hoạch với DaySim.
- **PASS**: bảng ngoài Canvas/HUD, không che nhân vật/thanh oxy/Máu/đồng hồ;
  không tràn ngang và bảng sáu mục tiêu nằm trong viewport 1280×720.
- **PASS**: Gather độc lập không phát sinh kế hoạch giả.
- **PASS**: kiểm lại adapter sau các sửa cuối: **5 tests**, 0.112 giây, 0 fail/error;
  [final-adapter-tests.txt](../proof/daily-quest/final-adapter-tests.txt).
- **PASS**: kiểm whitespace trên các file task. `git diff --check` toàn workspace
  còn báo hai dòng trailing whitespace ở `docs/verification/phase-3.md` vốn đã có
  thay đổi trước task; giữ nguyên file người dùng.

Ảnh: [Day 1 ban đầu](../proof/daily-quest/day1-empty-1280x720.png),
[sau bắt/hái](../proof/daily-quest/day1-collected-1280x720.png),
[hoàn thành](../proof/daily-quest/day1-complete-1280x720.png),
[Day 2](../proof/daily-quest/day2-1280x720.png),
[Day 3](../proof/daily-quest/day3-1280x720.png),
[Day 4](../proof/daily-quest/day4-1280x720.png),
[Day 5](../proof/daily-quest/day5-1280x720.png).

## Giới hạn và phần chưa xác minh

- **PARTIAL (giới hạn cũ của demo)**: adapter web vẫn chưa nối Shop thật và không
  chạy trực tiếp DaySim. Không mở rộng Day Loop/Shop trong task UI này.
- Browser dùng fixture đồng hồ/vị trí để kiểm nhanh, giỏ khởi tạo và mất hàng được
  dựng rõ trong verifier. Thu thập dùng phím trình duyệt, HTTP và simulation thật;
  các lần đổi ngày bỏ qua thời gian ca qua fixture ranh giới Shop rồi gọi action thật.
  Không tuyên bố đã chơi tay trọn năm ngày hoặc thắng toàn bộ kế hoạch trong 180 giây.
- **NOT VERIFIED**: phiên chơi tay liên tục năm ngày, thiết bị di động và FPS benchmark.
  Faint/cá sấu kiểm bằng suite simulation hiện có; browser kiểm giảm tiến độ bằng mất
  cá thể fixture, không tuyên bố có thao tác né/đánh cá sấu thủ công.

## Chạy lại và Git

```powershell
.venv\Scripts\python.exe docs/proof/phase-2/day_fixture.py --real-scenes --days 5 --port 8783
```

Mở http://127.0.0.1:8783/ → Chơi → Ra bến. Thêm `--scenario file.json`
để dùng `day.day_plan`/`gather.hold` theo schema chính thức.
Đã mở server bản sửa tại cổng 8783 (PID 12928); phiên cũ cổng 8782 giữ nguyên.

Git: các file task được sửa/thêm, chưa stage/commit/push; không merge hoặc đổi nhánh.
Commit đề xuất: `fix(ui): hiển thị nhiệm vụ nguyên liệu từ Day 1 theo kế hoạch backend`.
