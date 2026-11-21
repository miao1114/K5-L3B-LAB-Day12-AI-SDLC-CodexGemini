# Bàn giao cuối lên main

Người phụ trách yêu cầu chỉ hoàn thiện hồ sơ và đưa code lên main, **không chạy
thêm test, benchmark, soak hoặc browser** trong lượt chốt này. Các kết quả dưới đây
được tái dùng từ log thật, không phải lần chạy mới.

- Manifest: v1.3, team_size=6, bench_cmd/soak_cmd là các module có thật.
- P4-A: avg60.0015/p1 low53.6269/load964.65ms; 1801 frame/30.0159s.
- P4-B: 10/10 ngày, 0 crash hai lượt, deterministic trừ duration.
- P4-C: 8 test warning/contrast, 3 test live và browser regression đã PASS.
- P4-D: full 303/304 trước sửa assert version cũ, nhóm Quán chạy lại 22/22 PASS.
- Clone/ZIP ứng viên d251401 chạy trên Chrome/Windows; Linux/macOS NOT VERIFIED.
- MIT do người dùng chọn; ảnh AI do người dùng xác nhận, nguồn ghi CREDITS.
- Phản tư đã có đủ đường dẫn sáu handle; hann1holic/rawser246 còn phần tự thuật
  cần thành viên xác nhận. Không tự ghi toàn bộ hồ sơ đã hoàn tất nghiệm thu.
- Main vừa có 3fd7cd3 (phản tư Hùng), đã ghép không xung đột trước push.

Không đổi runtime/gameplay trong lượt chốt, không chạy lại test, không tạo tag hoặc
GitHub Release. Package lịch sử vẫn trỏ đúng ứng viên d251401, không giả là ZIP
đã kiểm của commit tài liệu cuối. Dùng `git archive` nếu cần ZIP mới, việc kiểm lại
package cuối chưa được thực hiện do yêu cầu không chạy thêm test.

Đối chiếu nghiệm thu: `docs/verification/phase-4.md`; chi tiết release candidate:
`docs/notes/P4-D-Final-Integration-Release.md`. Đưa code lên main không đồng nghĩa
các mục NOT VERIFIED/PARTIAL đã tự chuyển thành PASS.
