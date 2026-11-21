# Phase 4 — ứng viên tích hợp, chưa phát hành

Baseline `9919bca`, nhánh updatelevel; source ứng viên được hash tại
`docs/proof/phase-4/p4-d/source-hashes.json`. P4-A/B/C có code và proof thật;
manifest mới chỉ đổi metadata/version/entrypoints, không đổi tuning hoặc renderer.

| AC | Yêu cầu | Bằng chứng/cách kiểm | Kết quả |
|---|---|---|---|
| AC-P4-01 | v1.3, 6 người, lệnh thật | game.contract.json, check_team.py | PASS |
| AC-P4-02 | Render Gather thật | bench.json + bench-evidence/frame-times.json; avg60.002/p1 53.627/load964.65 | PASS |
| AC-P4-03 | Soak 10 ngày, deterministic | soak.json, p4-b/verification.json: 10/10, 0 crash hai lượt | PASS |
| AC-P4-04 | Cá sấu gần | p4-c/warning-monster-contrast.png, verify_p4_c.py | PASS |
| AC-P4-05 | Oxy | p4-c/warning-oxygen-contrast.png | PASS |
| AC-P4-06 | Khách sắp bỏ đi | p4-c/warning-customer-contrast.png | PASS |
| AC-P4-07 | High Contrast | p4-c/browser-tests.txt, contrast-ratios.json | PASS |
| AC-P4-08 | Clone sạch macOS/Linux ≤3 lệnh | README; Windows clone/package test ở p4-d/package-report.json khi tạo; Linux WSL không Python/Git | NOT VERIFIED trên macOS/Linux |
| AC-P4-09 | Regression | p4-d/regression-tests.txt: 303/304 pass, một test version cũ; sau sửa nhóm Quán 22/22 pass ở restaurant-regression.txt | PASS sau targeted fix; không chạy lại full |
| AC-P4-10 | ZIP chạy được, đúng commit | tools/package_release.py; release-artifacts/ và package-report.json | Chờ chạy package |
| AC-P4-11 | Main/tag/Release cùng SHA | chưa đưa ứng viên lên main, chưa tạo tag/Release | NOT VERIFIED |
| AC-P4-12 | Retro/reflections | retro có ghi nhận thực tế; thiếu hann1holic/thehung1406, file lunaHieu 490 từ, Ánh 214 từ, Hải thiếu phản tư | PARTIAL |

Không dùng trạng thái COMPLETE của notes A/B/C để tự chứng nhận Release. Không tái
chạy benchmark/soak dài vì implementation/tuning tương ứng không đổi; chỉ kiểm
metadata/entrypoints và raw metrics. Linux và hồ sơ thành viên còn là việc cần bổ sung.
