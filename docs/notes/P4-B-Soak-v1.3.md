# P4-B — Soak 10 ngày và tương thích v1.3

**Status: COMPLETE** theo yêu cầu P4-B được cung cấp. Baseline `9919bca`, nhánh
`updatelevel`. Code task chưa commit/push. Không triển khai benchmark/UI/release.

## A. Audit

- Trước sửa: `contract_version: 1.2`; TEAM/manifest đã có sửa riêng của người dùng
  (team_size từ 5 thành 6), và reflection Minh chưa track. Giữ nguyên các sửa đó.
- Đọc AGENTS, manifest, headless, DaySim/Shop, day_config, runner/Session, Gather,
  kho/IDs và test Day/inventory/stock. Repo chưa có TICKET-04_original; dùng yêu cầu
  P4-B đính kèm làm nguồn cho schema/lệnh soak, không tự suy diễn yêu cầu bot khác.
- `headless.py` chỉ nhận days 1–5; nhánh v11plus chỉ gồm 1.1/1.2 khiến Day v1.3 bị
  từ chối và mất đường chọn input v1.1. `contract.py` chỉ kiểm inventory khi ==1.2.
- `DaySim` không giới hạn số ngày ở constructor nhưng `_start_day` tra
  `self.plans[self.day]`, lỗi KeyError ở D6. Đóng sau `days_completed == days`,
  không có điều kiện cứng Summary tại D5 trong simulation.
- Một `DaySim` giữ Streams và IdRegistry cả lượt. `_start_day` reset timer, giỏ,
  HP/oxy theo cấp đang áp dụng; không reset economy/upgrades/IDs. Shop dùng `_buy`
  thật, đóng theo input shop_done hoặc max_ticks. Chỉ lúc Shop đóng mới cộng ngày.
- Có bot cho web mở rộng, nhưng task này không dùng luật stack/Auto End/unlock/
  map web. Theo prompt, input trung tính và timer thật đủ để hoàn tất các pha.

## B. Implementation và file thay đổi

| File | Thay đổi |
|---|---|
| `chonoi/contract.py` | Inventory validation v1.2 áp dụng tương đương v1.3 |
| `chonoi/headless.py` | v1.3 dùng cùng Day/input/mua hàng/tập kind v1.1+; giới hạn days chuẩn vẫn 1–5 |
| `chonoi/sim/day.py` | Thêm repeat_plans=False mặc định; khi bật chọn `(day-1) % 5`, snapshot plan.day vẫn là ngày thật |
| `chonoi/soak.py` | CLI, SoakSession, loop thật, schema output, xử lý lỗi và ghi JSON nguyên tử |
| `tests/test_soak.py` | 8 test tập trung, cả state/IDs, version, schema, crash và CLI |
| `tools/verify_p4_b.py` | Hai lượt CLI thật dùng manifest v1.3 riêng, đối chiếu gameplay và lưu proof |

`SoakSession` chỉ tạo **một** Session/DaySim rồi bật cyclic lookup trước gameplay;
không dựng lại sim theo ngày. Không đổi runner chuẩn hoặc logic nấu/decay/RNG.
Sau mỗi bước, chỉ ghi result nếu counter days_completed tăng. Kết quả lấy trực tiếp
từ earned/reputation/score của sim tại Shop đóng. Khi có exception, dừng, ghi số ngày
thật đã xong, crashes=1, traceback và exit 1; không bỏ qua lỗi để chạy tiếp.

Schema gốc đúng năm khóa `days,days_completed,crashes,results,duration_s`; result
đúng bốn khóa `day,earned,reputation,score`. Duration dùng perf_counter để đo thời
gian chạy, không dùng quyết định gameplay. Không thêm trường riêng vào JSONL chuẩn.
Đầu vào sai: exit 2, không ghi file; lỗi chạy/ghi: exit 1. Không cho out trùng manifest.

CLI không có option rút ngắn ca/scenario. Test nội bộ dùng tuning/scenario nhỏ và
input_provider của Python để kiểm state nhanh; không ảnh hưởng lệnh soak thật.

## C. CLI và bàn giao P4-D

Giá trị **soak_cmd** chính xác:

```json
"soak_cmd": "python3 -m chonoi.soak"
```

```powershell
python3 -m chonoi.soak --seed 7 --days 10 --out soak.json
```

P4-D cần chốt `contract_version: "1.3"` và thêm soak_cmd trên vào manifest khi
tích hợp Phase 4. **Task này không sửa manifest hoặc README** vì thuộc owner P4-D;
manifest working tree hiện vẫn 1.2, các thay đổi team_size có sẵn được giữ nguyên.
Soak hỗ trợ cả 1.2/1.3. V1.3 đã chạy thật bằng option `--contract` trỏ manifest riêng,
không chỉ thử thay chuỗi trong mock hoặc tự đổi file nhóm.

## D. Test results — bằng chứng thật

Windows Python 3.14.10 trong `.venv`, UTF-8. Không chạy Playwright, benchmark hoặc UI.

```powershell
$env:PATH = (Join-Path $PWD '.venv\Scripts') + ';' + $env:PATH
$env:PYTHONPATH = 'tests;.'
$env:PYTHONUTF8 = '1'
python3 -m unittest test_soak test_day test_inventory_v12 test_restaurant_stock -q
python3 tools/verify_p4_b.py
python3 -m unittest discover -s tests -v
```

- Targeted: **38 tests PASS**, 8.070 s, không fail/error.
- Regression cuối chạy **một lần: 299 tests PASS**, 37.522 s, không fail/error.
  Log: [regression-tests.txt](../proof/phase-4/p4-b/regression-tests.txt).
- Hai tiến trình CLI độc lập, mỗi tiến trình mô phỏng đủ **10 ngày liên tục**
  trong một Session (không gọi 10 phiên game). Dùng cùng manifest v1.3 và seed 7,
  duration ca/timer/spawn chuẩn; không cấp tiền/hàng, teleport, hoặc bỏ pha.

Lệnh thực tế của mỗi lượt, sau khi verifier tạo bản manifest v1.3 riêng:

```powershell
python3 -m chonoi.soak --seed 7 --days 10 --out docs/proof/phase-4/p4-b/soak-a.json --contract docs/proof/phase-4/p4-b/contract-v1.3.json
python3 -m chonoi.soak --seed 7 --days 10 --out docs/proof/phase-4/p4-b/soak-b.json --contract docs/proof/phase-4/p4-b/contract-v1.3.json
```

| Lượt | days | days_completed | crashes | results | duration_s |
|---|---:|---:|---:|---:|---:|
| A | 10 | 10 | 0 | 10, D1–D10 | 5.2189902000000075 |
| B | 10 | 10 | 0 | 10, D1–D10 | 5.236029499999859 |

**Determinism PASS:** tất cả trường bằng nhau trừ duration_s. Input trung tính giữ
nhân vật tại bến, Gather hết giờ, Quán kho rỗng hết giờ, Shop hết giờ. Vì vậy cả
10 result đều earned=0, reputation=3.0, score=300: đây là kết quả simulation thật,
không hard-code. Test riêng có payment, mua nâng cấp và item thu thập để tránh
dùng soak không phát sinh tiền/ID làm bằng chứng duy nhất cho persistence.

### Coverage của test riêng

- 10 ngày fixture đi đủ 30 cặp ngày/pha; cùng sim, Streams và IdRegistry;
  D6 dùng dishes D1, D10 dùng ingredients D5, plan.day=6/10 đúng ngày thật.
- days_completed chưa tăng khi đang Shop; chỉ ghi đủ kết quả sau Shop đóng.
- Fixture có thanh toán thật +60/ngày, tiền đầu 1000, mua oxy 200: sau D10
  money=1400, earned=1600; D6 bắt đầu money=1100/earned=1300, uy tín không reset.
  Oxy 1800 ở D1, 2700 từ D2 đến D10; upgrades giữ nguyên.
- Hái thực trên node fixture mỗi ngày cấp I1… I10, không reset ở D6;
  hàng dư vẫn bỏ sau Shop, giỏ ngày mới làm lại đúng luật hiện có.
- Kho rỗng, thiếu tiền nâng cấp, hết giờ, invalid args, out trùng manifest và
  lỗi ghi đều có kiểm. Inject exception D3 → đúng 2 kết quả, crashes=1 và CLI exit 1.
- Contract v1.3 thiếu inventory bị từ chối như v1.2. Headless main v1.3 chạy cả
  gather/quan/day trên engine thật; JSONL byte-identical với v1.2 ở cùng input.
  Headless chuẩn vẫn từ chối days=6 (exit 2).

Proof: [soak.json](../proof/phase-4/soak.json),
[soak-a.json](../proof/phase-4/p4-b/soak-a.json),
[soak-b.json](../proof/phase-4/p4-b/soak-b.json),
[verification.json](../proof/phase-4/p4-b/verification.json).
Artifact `phase-4/soak.json` được tạo mới khi chưa tồn tại; verifier không ghi đè
file primary của thành viên khác. Các proof riêng trong p4-b thuộc task này.

## E. Remaining issues / giới hạn

Không còn lỗi bắt buộc P4-B được phát hiện trong kiểm chứng. Cần P4-D tích hợp
manifest trước bàn giao chính thức. Soak mặc định không kiểm chiến thuật chơi/bán
hàng trong stress run; prompt cho phép input trung tính và phần state được test
riêng. Không chứng nhận các mục v1.3 ngoài phạm vi được cung cấp (benchmark, alerts,
high contrast, đóng gói/tag/Release); không có TICKET-04 gốc trong repo để đối chiếu
các mục đó. Chế độ Day/web chuẩn không được mở giới hạn >5 ngày.

Git: giữ nhánh `updatelevel`, không merge/tag/push/commit. TEAM, metadata team_size
và reflection Minh là thay đổi có sẵn, không đưa vào phạm vi sửa code P4-B.
