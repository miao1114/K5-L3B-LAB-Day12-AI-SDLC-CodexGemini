# Menu Unlock & Resource Spawn

Trạng thái: **PASS** — gameplay mở rộng web; nhánh `FRESHNESSPRICING`, HEAD `9e5546d`.
Chưa commit/push. Không sửa manifest hoặc luật headless chuẩn trong task này.

## Vấn đề và triển khai

Trước sửa, kế hoạch web đổi theo ngày nhưng Gather vẫn dùng đủ ba loài cá/ba loại
cây từ preset. Quán chỉ lấy món trong kế hoạch; chưa có nguồn cấu hình mở khóa chung.
Người chơi Day 1 vì vậy gặp nguyên liệu không dùng được.

`chonoi/web/gameplay.json.menu_unlocks` nay là nguồn thứ tự mở khóa duy nhất.
`interactive_menu.py` dùng cấu hình này tính menu cộng dồn và union recipe. Cùng menu
được dùng cho spawn, kiểm tra plan, Quán, khách gọi, preview món nấu được và UI.
Menu được mở khác với kế hoạch thu thập: khách vẫn có thể gọi món đã mở ngoài plan,
không giới hạn số khách bằng số suất mục tiêu.

| Ngày | Thêm món | Tổng món | Tập nguyên liệu Gather |
|---|---|---:|---|
| 1 | Gỏi bông súng, cá lóc nướng trui | 2 | cá lóc, bông súng |
| 2 | Cá kèo nướng | 3 | như D1 + cá kèo |
| 3 | Canh chua cá lóc | 4 | như D2 + bông điên điển |
| 4 | Lẩu cá linh điên điển | 5 | như D3 + cá linh |
| 5 | Lẩu mắm | 6 | như D4 + kèo nèo |

## Giữ mật độ và luật hiện có

- Không lọc bỏ thực thể sau khi sinh. Chỉ giới hạn tập loài trong bản sao tuning
  web **trước** khi Gather sinh cá. `random.choices` qua Streams hiện có chuẩn hóa
  trọng số trên các loài hợp lệ; không thêm RNG toàn cục.
- Mọi ngày giữ **8 đàn đầu ca**, **trần 12**, **360 tick/lượt**, cùng fish_spawn_x,
  depth hợp lệ của từng loài, hướng/di chuyển và kiểm khoảng trống hiện có.
  Day 1 có 12 vị trí spawn cá lóc hợp lệ để chọn 8 vị trí khác nhau.
- Giữ **6 điểm cây**, nguyên ID/vị trí; phân phối vòng tròn các loại cây đã mở
  trên sáu điểm. Day 1 cả sáu là bông súng. Regrow vẫn **1200 tick**.
- Cá sấu không phụ thuộc pool nguyên liệu: 1 con D1–2, 2 con từ D3;
  waypoint, hành vi và thông số không thay đổi.
- Yield linh 3/kèo 2/lóc 1, stack linh, item IDs, freshness và file kho giữ nguyên.
  Scenario web có fish/nodes tường minh chứa loại chưa mở bị từ chối rõ ràng;
  không âm thầm xóa thực thể. Giỏ scenario có sẵn vẫn giữ item thật.

## Kế hoạch và UI

Plan web tăng **2→3→4→5→6 suất**; nguyên liệu tính lại từ recipe.
Số ô cần khi bắt nguyên đàn: **3/5/7/9/12**, đã tính kèo lấy cả đàn và linh theo stack.
D5 dùng lóc nướng ×3, gỏi ×1, lẩu linh ×1, lẩu mắm ×1. Không ép mỗi món đã mở
phải có một suất mục tiêu vì cả sáu recipe cùng lúc cần vượt 12 ô. Canh chua/cá kèo
vẫn có thể được khách gọi ở D5 nếu đủ hàng. Bông súng giữ mục tiêu 2 mỗi ngày.

Scenario ghi đè một phần kế thừa **plan web** ở các ngày còn lại, không vô tình
lấy plan chuẩn có món chưa mở. Plan chứa món khóa hoặc vượt sức chứa bị từ chối.
UI nhiệm vụ hiện có giữ nguyên; thêm danh sách món đã mở ở DayIntro/Quán và thông
báo “Đã mở khóa món mới!” khi sang ngày mới. Món khóa không xuất hiện trong danh sách
có thể nấu. Giá/công thức không sửa.

## File thay đổi trong lượt này

- Thêm `chonoi/interactive_menu.py`, `tests/test_interactive_menu.py`,
  `tools/verify_menu_unlock_browser.py`.
- Sửa `chonoi/interactive.py`, `chonoi/interactive_web.py`,
  `chonoi/web/gameplay.json`, `chonoi/web/day-plan.json`, `chonoi/web/index.html`.
- Hai verifier interactive nhận đường dẫn proof riêng; fixture bắt linh của browser
  chuyển sang D4 đúng ngày mở khóa. README và notes này cập nhật cách kiểm tra.
- Các thay đổi chưa commit từ task trước và thay đổi riêng TEAM/manifest/docs giữ nguyên.

## Kết quả thực tế

Proof riêng: `docs/proof/menu-unlock/`; không ghi đè bằng chứng Phase 1–4.

- **PASS:** nhóm tập trung ban đầu **33 tests**, 1.626 s.
- **PASS:** regression toàn bộ chạy **một lần: 250 tests**, 38.399 s, 0 fail/error.
  `regression-tests.txt` gồm CLI/JSONL/seed/schema/headless và các module cũ.
- Sau thêm xử lý scenario một phần: **PASS 34 targeted tests**, 1.307 s,
  `final-targeted-tests.txt`. Không tuyên bố đã chạy lại full suite 251 test.
- **PASS:** test spawn mọi ngày: 8 đàn đầu, vị trí không trùng, loài/độ sâu hợp lệ,
  spawn ở tick 360/720/1080/1440 rồi dừng tại 12; sáu cây, hồi đúng tick;
  quái khớp Gather chuẩn của cùng ngày, tuning gốc không bị mutate.
- **PASS:** khách/menu/quest cùng unlock, món đã mở ngoài plan vẫn được gọi;
  scenario chuẩn và preset day_plan không đổi.
- **PASS:** replay 5 ngày seed 1 với spawn mới, movement/oxy/quái/Shop thật,
  thu đủ mục tiêu trong **11.72/11.82/28.67/35.38/53.45 giây**, ô dùng 3/5/7/9/12;
  hoàn tất 5 ngày sau 24.139 tick; replay cùng input có event/summary giống nhau.
  `progression-report.json`, `progression-log.txt`, `progression-events.jsonl`, inputs.
- **PASS:** Chrome 1280×720 qua API và nút chuyển cảnh thật: mở 2/3/4/5/6 món,
  8 cá/6 cây mỗi ngày, thông báo mở món và menu Quán đúng. Không pageerror/console
  error. `browser-report.json`, ảnh `day1-only-usable-resources.png`, `day1-unlock.png`
  đến `day5-unlock.png`. Fixture đồng hồ chỉ để chạy nhanh, không cấp cá/kho giả.
- **PASS:** verifier tích hợp stack/Auto End/Shop chạy sau đổi unlock;
  `integration-browser-report.json`. Browser bắt 2 đàn linh đúng D4, ca 1 bông súng
  D1 vẫn đóng đúng, replay qua đủ màn 5 ngày và kết quả trùng backend.
- Lần browser đầu phát hiện ID HTML trùng giữa panel Quán ẩn và DayIntro;
  đã đổi sang class và kiểm lại **đúng nhóm browser**, không chạy lại toàn suite.

```powershell
$env:PATH = (Join-Path $PWD '.venv\Scripts') + ';' + $env:PATH
$env:PYTHONPATH = 'tests;.'
$env:PYTHONUTF8 = '1'
python3 -m unittest test_interactive_menu test_interactive_gameplay test_phase2_live_preview -v
python3 tools/verify_interactive_progression.py docs/proof/menu-unlock
python3 tools/verify_menu_unlock_browser.py
```

Chơi: `python3 docs/proof/phase-2/day_fixture.py --real-scenes --days 5 --port 8783`.
Mở http://127.0.0.1:8783/ → Chơi. `--contract-plan` giữ đường preview chuẩn cũ;
headless không import luật unlock/pool web, không thay contract_version, manifest,
RNG chuẩn, schema inventory hoặc JSONL.

Giới hạn: kiểm khả thi gameplay với seed 1, không bảo đảm mọi seed/chiến thuật đều
đạt mục tiêu. Kế hoạch là mục tiêu dự kiến; khách gọi ngẫu nhiên có thể dùng nguyên
liệu theo cơ cấu khác và để dư hàng. Không có chức năng bắt buộc còn bỏ dở.
