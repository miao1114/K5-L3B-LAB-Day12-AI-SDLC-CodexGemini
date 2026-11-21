# P4-A — Real Render Benchmark

**Status: COMPLETE.** Nhánh `updatelevel`, nền `9919bca`; chưa commit/push.

## A. Audit

Đối chiếu AGENTS/README, LiveGame/LiveServer, renderer, Session và tool Playwright
đang có. Chưa có benchmark. `frame()` gọi rAF liên tục nhưng chỉ `draw()` khi dirty,
nội suy hoặc Day đang chơi; số callback không phải số khung hình vẽ.
Backend live có thể khởi chạy Gather lõi bằng tuning manifest, không cần adapter web
200 m/stack/unlock. Asset dùng đường /art và renderer hiện có. Playwright và Chrome
đã có trong venv/máy. Không thay simulation, manifest, README, P4-B hoặc luật P4-C.

## B. Implementation

- `chonoi/bench.py`: CLI, điều phối server/browser, công thức, kiểm đầu vào và output.
- `tests/test_bench.py`: 5 test công thức/schema/CLI, sample nhỏ, frame rất chậm,
  ceil 1% và frame time không đều.
- `chonoi/web/index.html`: chỉ ba điểm instrumentation: cờ query chính xác
  `?benchmark=render`, ép dùng cùng `draw()` liên tục khi game active, callback
  timestamp sau khi toàn bộ drawGather + drawLabels hoàn tất. Đường chơi bình thường
  không có cờ giữ nguyên. Không đếm callback khi draw trả sớm vì không có cảnh.

Giá trị P4-D khai vào manifest:

```json
"bench_cmd": "python3 -m chonoi.bench"
```

```powershell
python3 -m chonoi.bench --seed 42 --duration 30 --out docs/proof/phase-4/bench.json
```

Runner tạo LiveGame("gather") từ manifest thực, không dùng InteractiveDayWeb,
không lọc cá/cây hoặc thay giới hạn. Nhân vật không nhận input, ở dock. Cá bơi,
cá sấu/hiệu ứng/animation/freshness vẫn chạy. Không dùng screenshot làm frame.

Browser inject wrapper drawImage để xác nhận đã vẽ asset nhân vật, cá và cá sấu
trên Canvas world. Readiness callback chỉ nhận sau draw thật; page load còn chờ
resource trang. `load_ms` đo bằng Python perf_counter **trước khởi chạy server/
browser** đến khi browser xác nhận completed ready frame. Bao gồm overhead xác nhận
và polling, là phép đo bảo thủ; không trừ chéo đồng hồ Python với JavaScript.

Warm-up >=3 giây kể từ ready. Timestamp anchor bắt đầu cửa sổ đo; mỗi draw hoàn tất
sau anchor cho một frame time liên tiếp. Chốt ở draw đầu đạt duration thực; mọi
interval đều nằm giữa anchor và end, không lấy khoảng trước warm-up/sau đo.
`frames=len(intervals)`, `measured_s=(end-start)/1000`, `avg_fps=frames/measured_s`.
1% low dùng `1/mean(slowest max(1,ceil(.01*frames)) intervals)` theo yêu cầu, không
dùng percentile FPS. Frame-times thô lưu riêng, không thêm trường vào bench.json.

Một screenshot lấy ngay sau bắt đầu đo; chi phí screenshot có thể tạo outlier thật
và được giữ trong số liệu. Không ẩn thực thể hoặc giảm hiệu ứng để làm xanh.
Browser/server luôn đóng trong finally. Thiếu Playwright/browser, thiếu frame,
pageerror hoặc cấu hình sai trả exit khác 0, không ghi báo cáo thành công giả.

## C. Results

Test đã chạy:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_bench.py -v
.venv\Scripts\python.exe -m chonoi.bench --seed 42 --duration 2 --out docs/proof/phase-4/bench-smoke.json
.venv\Scripts\python.exe -m chonoi.bench --seed 42 --duration 30 --out docs/proof/phase-4/bench.json
.venv\Scripts\python.exe -m unittest discover -s tests -p test_live.py -q
```

- **5 unit tests PASS**, 0.009 s.
- **Smoke PASS:** 121 frame / 2.0157 s, avg 60.0288, p1 low 54.3478, load 1463.22 ms.
- **3 live regression tests PASS**, 1.245 s (state/input/restart/assets/kho).
- Benchmark 30 giây chạy **đúng một lượt**, không chạy soak/benchmark gameplay khác
  hoặc toàn suite không liên quan. Không cần tối ưu renderer vì đã đạt mục tiêu.

| Chỉ số chính thức | Số đo thật | Mục tiêu | Kết quả |
|---|---:|---:|---|
| avg_fps | 60.00153252109641 | ≥60 | PASS |
| p1_low_fps | 53.626869884095605 | ≥30 | PASS |
| frames | 1801 | >0 | PASS |
| measured_s | 30.01590000000037 | khoảng 30 s | PASS |
| load_ms | 964.6535000001677 | ≤10000 | PASS |

Warm-up chính thức 3.0155 s. JSON đúng năm trường; raw frame times cho phép tính
lại avg và 1% low. Snapshot cuối có simulation tick tiến thực, nhân vật vẫn ở dock.

## D. Evidence và môi trường

- `docs/proof/phase-4/bench.json`: số đo chính thức.
- `docs/proof/phase-4/benchmark-scene.png`: bản sao ảnh thật của lượt đo chính thức.
- `docs/proof/phase-4/benchmark-environment.md`: phương pháp/môi trường.
- `docs/proof/phase-4/bench-evidence/`: ảnh gốc, environment.json, frame-times.json
  và benchmark-environment.md. Smoke có thư mục bench-smoke-evidence riêng.
- Windows 11 build 26200; Chrome **157.0.8103.80**, headless với Canvas thật,
  viewport **1280×720**, DPR **1**. Canvas theo layout game hiện có: CSS **672×378**,
  backing buffer **672×378**. Không khai Canvas 1280×720; 1280×720 là viewport gồm
  HUD/sidebar. Không giảm resolution so với đường chơi cùng viewport.
- Cảnh vẫn đầy đủ background, Út Sen, cá/cá sấu; không ảnh menu/splash. Không lỗi
  JavaScript được ghi nhận. Không đo renderer Python hoặc dùng timer cộng frame giả.

## E. Remaining issues / handoff

Không có blocker P4-A còn lại. P4-D thêm bench_cmd trên vào manifest/README và dùng
proof để tổng hợp verification; chưa đổi version, tag hoặc Release.

FPS phụ thuộc scheduling, refresh rate, headless Chrome, tải máy và chi phí chụp ảnh;
đây là kết quả máy hiện tại, không cam kết thiết bị khác. Xác nhận CPU đã phát lệnh
Canvas đầy đủ, không phải đo thời điểm GPU trình bày vật lý lên màn hình. Một smoke
trước đó có thể làm ấm cache OS; lượt chính thức vẫn dùng browser context mới.
Không chứng nhận các phần v1.3 ngoài nội dung TICKET-04 được người dùng cung cấp.

Chỉ thay ba dòng instrumentation trong file UI dùng chung, giữ nguyên P4-C và các
thay đổi chưa commit khác. Không merge/tag/push/commit trong lượt này.
