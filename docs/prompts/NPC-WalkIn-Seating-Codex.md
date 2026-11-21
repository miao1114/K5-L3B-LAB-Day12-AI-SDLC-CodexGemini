# FEATURE — NPC WALK-IN → SEAT → EAT → WALK-OUT (QUÁN)

## Mục tiêu

Bạn là Senior Canvas 2D Game Engineer. Hãy **triển khai code thực sự**, không dừng ở phân tích, cho trò chơi **Quán Ăn Chợ Nổi** tại repo:

`https://github.com/miao1114/K5-L3B-LAB-Day12-AI-SDLC-CodexGemini`

**Tình trạng thực tế đã quan sát trên nhánh main lúc chuẩn bị task:** `chonoi/web/index.html` đang có `drawQuan()`, tải các bàn `ban-mot`, `ban-hai`, `ban-ba`, `ban-bon` và vẽ khách trực tiếp tại bàn bằng `drawSprite(guests[...])`. `guests` là các sprite `khach-nam`, `khach-nu`. `chonoi/live.py` trả snapshot qua `/state` và phục vụ asset trong `chonoi/web/art`. **Phải kiểm tra lại working tree mới nhất** vì code có thể đã thay đổi sau thời điểm này.

**Yêu cầu người chơi:** khi khách đến Quán, thấy NPC nam/nữ đi từ cửa vào quán, đi tới đúng bàn T1–T4, chuyển tư thế ngồi, chờ món, ăn, sau đó đứng dậy đi ra cửa. Không xuất hiện tức thì ở bàn nữa.

## 1. Audit tập trung trước khi code

- Kiểm tra `git status`, HEAD và `AGENTS.md` (nếu có), bảo toàn thay đổi chưa commit.
- Đọc **chỉ các vùng liên quan** trong `chonoi/web/index.html`: `loadSprite`, `drawSprite`, `drawQuan`, `frame`, `requestAnimationFrame`, `poll`, `snap`, `previousPose`, `drawCustomerBar`, `drawReservation`, `drawLabels`, `tableForOrder`, world→Canvas projection, và xử lý Day mode / pause.
- Kiểm tra `chonoi/live.py` route asset và `/state`, `chonoi/sim/quan.py` hoặc customer module để biết `customers[].id`, `table_id`, `state`, timer, events `customer_arrived`, `customer_left`, `paid`, v.v. **Chỉ dùng event có thật**.
- Mở và xem `chonoi/web/art/quan-nen.webp` để xác định cửa/điểm vào, và **bốn ảnh bàn hiện có** để chọn đúng tọa độ ghế/ngồi. Nếu cửa không rõ trên ảnh nền, chọn một vị trí vào hợp lý nhất trên mép cảnh, ghi rõ cấu hình, không tự bịa một cửa khác trên background.
- Giữ các phần UI đã có: thanh xanh/vàng/đỏ trên đầu khách; nhãn bàn T1–T4; nhãn bàn trên đầu Bà Út khi cầm món; hệ thống cảnh báo/high contrast nếu có.

## 2. Assets đã chuẩn bị — copy vào repo

Trong gói ZIP, đã có 4 sprite `.webp` RGBA:

| File | Bố cục | Cell (px) | Ý nghĩa |
|---|---|---|---|
| `chonoi/web/art/khach-nam-di-bo.webp` | 5 cột × 3 hàng | 260×404 | Nam đi bộ: hàng 0 nhìn xuống, hàng 1 nhìn lên, hàng 2 nhìn ngang phải (lật cho trái) |
| `chonoi/web/art/khach-nu-di-bo.webp` | 5 cột × 3 hàng | 260×404 | Nữ đi bộ: cùng cấu trúc |
| `chonoi/web/art/khach-nam-ngoi.webp` | 4 cột × 1 hàng | 418×471 | Nam ngồi: 0 chờ, 1 vui/chào, 2 ăn, 3 uống |
| `chonoi/web/art/khach-nu-ngoi.webp` | 4 cột × 1 hàng | 418×471 | Nữ ngồi: cùng cấu trúc |

`docs/npc-sprite-map.json` đi kèm chứa metadata. Ảnh không có bàn để **không chồng bàn lên `ban-mot` ... `ban-bon`**. Khách có thể cởi nón lá khi ngồi; trang phục/phối màu vẫn nhận diện được.

- Dùng `loadSprite('khach-nam-di-bo')` v.v. để tận dụng loader có sẵn, tránh tải lại mỗi frame.
- Giữ `.webp` và tên **chữ thường + dấu gạch nối**, vì server hiện chỉ nhận `/art/[a-z-]+\.webp`.
- Giữ `khach-nam.webp` và `khach-nu.webp` hiện hữu làm fallback nếu các ảnh mới chưa load.
- **Không dùng** bộ ảnh khách ngồi kèm cả bàn, vì mỗi bàn T1–T4 đã có asset riêng.
- Dùng atlas source crop chuẩn: `sx=col*cellW`, `sy=row*cellH`, `sw=cellW`, `sh=cellH`.

## 3. Frontend state machine độc lập với gameplay

Tạo một visual-only controller, ví dụ `NpcWalkController`, quản lý theo **identity khách hàng** (ID từ snapshot kết hợp session/day token nếu cần), không dùng `table_id` làm identity. Trạng thái hiển thị:

1. `entering`: sinh avatar tại vị trí cửa rồi đi qua waypoints đến bàn được giao.
2. `sitting`: chuyển 150–300ms từ sprite đi bộ sang sprite ngồi; dùng pose chờ.
3. `waiting`: hiển thị tư thế ngồi/chờ; thanh kiên nhẫn dựa vào **snapshot**, không tự đếm gameplay.
4. `eating`: khi `customer.state === 'eating'`, dùng pose ngồi ăn (có thể thỉnh thoảng chuyển uống); thanh vàng dựa vào timer thật.
5. `leaving`: sau khi khách rời/tất toán/bỏ đi, **lưu bản sao visual** tạm, đứng dậy và đi ngược về cửa, sau đó xóa visual state.

**Không thay đổi** thời gian đến, thời gian kiên nhẫn, món, giữ chỗ, phục vụ, thanh toán, reputation, tiền tip, phân bàn, snapshot JSONL hoặc logic headless. Nếu khách đã `waiting` trong backend khi đang đi bộ, timer backend vẫn chạy đúng như cũ. Đây là hoạt ảnh minh họa, không thêm thời gian gameplay.

### Xử lý vòng đời & đồng bộ

- Tạo visual khi thấy **ID khách mới** (event hoặc diff giữa hai snapshot), **không tạo lại ở mỗi lần poll**.
- Khi refresh trang giữa một ca, nếu snapshot ban đầu đã có khách `waiting/eating`, **hydrate trực tiếp tại bàn** (không phát lại cảnh vào cửa cho khách đã ngồi trước lúc trang tải).
- Khi `paid`, `customer_left`, `reservation_failed` hoặc khách biến mất khỏi snapshot (tùy event thực sự có), bắt đầu `leaving` đúng một lần và giữ pose cuối trong cache cho tới khi đi ra khỏi cảnh.
- Không để ghost NPC sau restart, chuyển ca, DayResult, Shop hoặc khi customer ID được tái sử dụng ở ngày mới.
- Nếu cùng bàn có khách mới khi khách trước vẫn đang đi ra, hai nhân vật hiển thị tách biệt nhưng **bàn trong simulation thuộc khách mới**; không giữ bàn vì animation.
- Nếu khách rời trước khi đi đến bàn do hết patience, chuyển thẳng từ vị trí hiện tại sang đường đi ra.
- Nếu khách mới được phục vụ trong lúc đang `entering`, ưu tiên giữ logic simulation và rút ngắn/snap animation an toàn.
- Khi pause, đóng băng tiến độ visual; resume tiếp tục, không nhảy theo `performance.now()` đã trôi trong lúc pause.
- Với `prefers-reduced-motion`, sử dụng hiển thị tĩnh tại bàn và cập nhật status, không ép animation.

## 4. Đường đi: cửa → T1/T2/T3/T4

- Dựa vào `tables[].pos` và phép chiếu Canvas hiện có (`at(table.pos)`), không hardcode **vị trí màn hình cuối** cho mỗi khách.
- Xác định `entryPoint` từ nền `quan-nen.webp` và một đường đi chung trong khu vực trống, chia nhánh đến đúng ghế; lưu ít nhất 1–2 waypoint ở **world coordinates** hoặc normalized scene coordinates để không cắt xuyên mặt bàn/bếp.
- Với bố cục lõi 4 bàn tại T1[9,2], T2[13,2], T3[9,6], T4[13,6], xác minh **thông số thực tế** từ snapshot trước khi cố định tọa độ; không tin tưởng các giá trị cũ nếu game đã thay đổi layout.
- Di chuyển mượt 8–10 FPS sprite, vận tốc thị giác khoảng 1–2 m/s tùy độ dài đường, tổng thời lượng đi đến bàn khoảng 0.8–2.2 giây, có thể chỉnh cấu hình.
- Trong khi đi, chọn hàng hướng nhìn (xuống/lên/ngang) theo vận tốc 2D; đi trái dùng mirrorX của hàng ngang.
- Không để NPC nhảy từ cửa đến bàn ở frame kế; chỉ snap/fallback nếu asset lỗi hoặc animation bị tắt.
- Không làm khách xuyên vật cản rõ ràng, bước ra ngoài canvas hoặc bị bảng HUD che. Khi resize, dùng tọa độ tương đối/world thay vì tọa độ pixel cố định.
- Nếu khách đứng trên ghế khác hướng, dùng offset ghế riêng theo bàn; mục tiêu là ngồi **phía sau mặt bàn đúng phối cảnh**, không đè lên bát, đũa và gia vị.

## 5. Layering — không vẽ thêm bàn lần thứ hai

Game hiện đã vẽ bàn qua `quanFixtures`, nên chỉ cần nhân vật. Ưu tiên:

- Với khách đi bộ: vẽ shadow nhẹ dưới chân và sprite theo anchor chân.
- Với khách đang ngồi: đặt sprite ở vị trí ghế thật, **phần thân dưới nằm sau mặt bàn**; dùng layering/clip hoặc lựa chọn order vẽ phù hợp với asset bàn.
- Bàn T1–T4 phải hiển thị **một lần duy nhất**. Không render ảnh ngồi có bàn thứ hai.
- `drawCustomerBar` nên bám theo **tọa độ visual hiện tại** (khi bước đi) và vị trí đầu sprite khi ngồi, không bám cố định vào bàn trong lúc avatar đang di chuyển.
- `drawReservation`, label bàn, label món và badge T1–T4 vẫn hiển thị đúng, không bị che.
- Khi đang ăn, người xem nhận ra nhân vật cử động/đổi tư thế. Không cần tạo tick mới cho simulation.

## 6. Vòng render

`requestAnimationFrame()` của frontend hiện có thể **chỉ vẽ khi invalidate**, trong khi ở mode `quan` độc lập không phải lúc nào cũng redraw mỗi frame. Hãy đảm bảo khi bất kỳ NPC đang `entering`, `sitting`, `eating-animation` hoặc `leaving`, Canvas **vẫn redraw để hoạt ảnh chạy**, ngay cả giữa các lần poll `/state`. Khi tất cả đứng yên, có thể giữ tối ưu redraw cũ.

- Tái sử dụng `drawSprite`, `loadSprite` và transform Canvas hiện có; dùng `save()/restore()` khi lật sprite.
- Không tạo `setInterval()` cho từng NPC, không tạo Image mới trong `drawQuan()`, không sửa loop sim 60 tick/s.
- Phân biệt thời gian animation (visual clock) và timer simulation.
- Giữ sprite size nhất quán khi đổi đi bộ ↔ ngồi, nhất là anchor chân/ghế.
- Nếu ảnh lỗi/404, fallback sprite khách hiện tại và ghi cảnh báo dev, không làm game crash.

## 7. Test tập trung, tiết kiệm token

Ưu tiên test logic mapper/state machine và một lượt thử browser:

- T1–T4: khách mới đều xuất hiện ở cửa, tới đúng bàn, ngồi sau bàn, thanh status vẫn đúng.
- Khách nam/nữ sử dụng đúng sheet; hướng đi tương ứng; không nhảy frame sai.
- Khách chờ→ăn→rời (paid), khách chờ→bỏ đi (patience), và đơn reservation thất bại nếu có.
- Hai khách đến cùng tick, bàn trống/được tái sử dụng, cùng ID ở ngày khác, DayIntro/Shop/restart.
- `--mode quan` riêng vẫn animate liên tục giữa các snapshot, `--mode day` cũng vậy.
- Pause/resume và reduced-motion; resize 1280×720, không chồng HUD.
- Không sửa gameplay/headless. Chạy targeted tests; **một** lượt regression cuối nếu cần. Không chạy benchmark/soak dài không liên quan.
- Test UI bằng browser nếu có công cụ; ảnh chỉ được xem là bằng chứng nếu chụp thật. Nếu không kiểm được browser ghi `NOT VERIFIED`.

## 8. Tài liệu bàn giao

Tạo `docs/notes/NPC-WalkIn-Seating.md` ghi: asset & frame mapping, tọa độ cửa/waypoints/ghế từng bàn, visual state transitions, thay đổi code, kết quả test, limitations, cách chạy web local.

Không ghi đè file `docs/verification/phase-4.md`, không chỉnh sửa P4-A/B/D, không tự merge/push/tag/release.

### Báo cáo cuối (ngắn gọn bằng tiếng Việt)

- Status COMPLETE / PARTIAL / BLOCKED.
- File thay đổi; asset đã copy.
- Luồng cửa→bàn→ngồi→ăn→đi ra có hoạt động không.
- Kết quả targeted tests/browser thật.
- Những vấn đề chưa xác minh.
- Git status và commit message đề xuất.

**Hãy trực tiếp triển khai đầy đủ, giữ nguyên hệ thống simulation và UI hiện tại. Không làm khách spawn trực tiếp vào bàn nữa khi họ mới đến trong phiên game đang chạy.**
