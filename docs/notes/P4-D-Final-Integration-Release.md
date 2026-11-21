# P4-D — Final Integration & Release Candidate

**Status: PARTIAL.** Không công bố release khi chưa đạt toàn bộ nghiệm thu.

## A–C. Audit, integration, contract

Nhánh updatelevel, nền 9919bca (origin/main lúc audit). P4-A/B/C có implementation
và proof thật ở working tree; P4-D tích hợp manifest 1.3, bench_cmd/soak_cmd tương
ứng module có thật. team_size giữ 6 theo xác nhận nhóm, không giảm về 5 theo mẫu.
extensions=[] giữ nguyên preset đang dùng; current/reservations có code/test và
web bật riêng, không tự thay policy chuẩn trong bước release.

Người dùng xác nhận ảnh tự tạo AI, chọn MIT cho mã nguồn; đã tạo LICENSE và bổ sung
CREDITS. Không tự cấp giấy phép bên thứ ba cho ảnh; cần tuân thủ điều khoản công cụ.
Không sửa luật gameplay. Test cũ yêu cầu version đúng 1.2 được cập nhật chấp nhận
1.2/1.3 kế thừa, giữ nguyên kiểm recipe/tuning; lỗi và lý do có trong proof.

## D. Verification

- Benchmark tái dùng code render không đổi: 1801 frame/30.0159 s, avg60.0015,
  p1 low53.6269, load964.65ms. Raw intervals tái tính đúng năm trường.
- Soak tái dùng v1.3 fixture cùng tuning: hai lượt 10 ngày, 0 crash,
  5.21899/5.23603 s, gameplay deterministic, không giả doanh thu.
- Warning/High Contrast: 8 browser test, 3 live regression, animation/HUD đa kích
  thước PASS. Không sửa cảnh báo khi tích hợp.
- Full regression đúng một lần: 304 test/46.233 s, một lỗi assert version cũ;
  sửa đúng compatibility rồi chạy lại nhóm restaurant: 22 test/6.154 s PASS.
- README có ba lệnh clone/cd/python, runtime stdlib. Không cần file bí mật.
  Windows clean clone/ZIP dùng tools/package_release.py, kết quả ghi package-report.json.
  WSL chỉ docker-desktop không có Python/Git; Docker daemon không chạy. Linux/macOS
  **NOT VERIFIED**, không suy ra đạt từ kết quả Windows.

## E–F. Packaging và release

`python tools/package_release.py` archive **đúng HEAD** bằng git archive, clone
local --no-local ở thư mục tạm và test browser/HTTP/asset từ cả clone lẫn ZIP.
ZIP trong release-artifacts (gitignore), SHA256/commit ghi tại proof p4-d.
Không kèm .git, venv, cache; snapshot commit không lấy file untracked ngoài Git.
Release notes: docs/release-notes-v1.0.0.md. Chưa đưa ứng viên lên main, chưa tạo
phase-4/v1.0.0 hay GitHub Release vì clean clone đa OS và reflections còn thiếu.
Không có tag công khai hiện hữu lúc audit; không xóa/ghi đè tag.

Sau khi nhóm bổ sung các mục còn thiếu: kiểm package commit ứng viên, đưa lên main,
fetch xác nhận remote SHA, tạo hai annotated tag cùng SHA rồi gh release create
v1.0.0 với package và release notes. Không dùng lệnh này trước khi đủ nghiệm thu.

## G–I. Hồ sơ và việc còn lại

README/CHANGELOG/CREDITS/LICENSE, verification, retro, AI log và clarify được cập
nhật theo bằng chứng. Giữ tài liệu phản tư gốc; không tự viết trải nghiệm cho
hann1holic/thehung1406 hoặc giả xác nhận review. Cần rút gọn lunaHieu/Ánh ≤200 từ,
bổ sung phần phản tư của Hải và chuẩn hóa tên file theo handle sau xác nhận.

Các thay đổi user ở TEAM/metadata/reflection giữ lại. Ứng viên là công việc chưa
phát hành; package test và SHA được xác định trong p4-d/package-report.json, không
bịa SHA, URL Release hoặc chứng nhận mọi hệ điều hành. Còn thiếu nghiệm thu Linux/
macOS và hồ sơ thành viên; không đánh dấu COMPLETE cho P4-D.
