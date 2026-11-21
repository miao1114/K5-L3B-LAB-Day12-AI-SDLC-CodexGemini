# Phase 3 — Verification Matrix (MẪU CHƯA CHẠY)

> **Không được đổi `NOT RUN` thành PASS khi chưa thực thi và lưu proof tại commit bàn giao.**
> Repo/branch/commit/tag: _điền sau khi có build tích hợp_  
> Contract: v1.2 · TICKET-03.  
> Ngày/giờ chạy, môi trường: _điền thực tế_.

| AC kiểm tra | Người | Trạng thái | Test/CLI đã chạy | Proof path | Ghi chú |
|---|---|---|---|---|---|
| Contract v1.2 và config freshness | P3-02 | NOT RUN | — | — | — |
| Kho items[] và validation exit 2 | P3-02 | NOT RUN | — | — | — |
| ID xuyên pha/Ngày | P3-02 | NOT RUN | — | — | — |
| Atomic inventory-out và faint empty | P3-01/02 | NOT RUN | — | — | — |
| Gather decay/spoiled/LIFO | P3-01 | NOT RUN | — | — | — |
| Quan decay/spoiled/re-reserve | P3-03 | NOT RUN | — | — | — |
| Cook price / consumed IDs / event | P3-04 | NOT RUN | — | — | — |
| Tip/payment/2 stoves/4 tables | P3-04 | NOT RUN | — | — | — |
| Smoke file Gather → Quan | Cả nhóm | NOT RUN | — | — | — |
| Smoke Day chuyển pha và nhiều Ngày | P3-02/03/04 | NOT RUN | — | — | — |
| UI freshness/spoiled local | P3-05 | NOT RUN | — | — | — |
| Regression P1/P2 còn hiệu lực | Cả nhóm | NOT RUN | — | — | — |
| CHANGELOG/ADR/retro/log AI | Cả nhóm | NOT RUN | — | — | — |
| Tag `phase-3` cùng commit đã test | Người được giao release | NOT RUN | — | — | — |

## Lệnh mẫu (cần xác nhận entrypoint repo thực tế)

```bash
PYTHONPATH=tests:. python3 -m unittest discover -s tests -v

# Fixture ngưỡng fresh 30, không input: spoiled ở tick 1
python3 -m chonoi.headless --mode gather --seed 42 \
  --scenario tests/fixtures/phase3/gather_threshold.json \
  --ticks 1 --out docs/proof/phase-3/gather_threshold.jsonl

# Ghi file kho từ dock đầu bước
python3 -m chonoi.headless --mode gather --seed 42 \
  --scenario tests/fixtures/phase3/gather_dock.json \
  --inputs tests/fixtures/phase3/gather_dock_inputs.json \
  --ticks 1 --out docs/proof/phase-3/gather_dock.jsonl \
  --inventory-out docs/proof/phase-3/stock.json

# Quán tick 0 chỉ dựng fixture, kiểm stock không bị hao tươi trong bàn giao
python3 -m chonoi.headless --mode quan --seed 42 \
  --inventory docs/proof/phase-3/stock.json \
  --ticks 0 --out docs/proof/phase-3/quan_tick0.jsonl
```

**Lưu ý:** Các lệnh trên là hướng dẫn chạy, **không phải bằng chứng đã chạy**. Không đính log giả. Kiểm chứng `day` chỉ khi P3-02 tích hợp xong, với lệnh phù hợp README và `--mode day --days 1`.

## Kết quả/biên bản

- Test tổng: _NOT RUN_
- Smoke file: _NOT RUN_
- Smoke day: _NOT RUN_
- Regression: _NOT RUN_
- Phần chưa đạt: _chưa xác định_
- Quyết định release: _chưa xác định_
