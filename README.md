# Scheduling_algorithm_in_multiprocessor_systems

Mục tiêu
-------
Trình mô phỏng đặt lịch CPU trên hệ đa bộ xử lý (multiprocessor). Dự án mô hình hoá tập các tiến trình, chạy nhiều thuật toán lập lịch (global, per-CPU, work-stealing, load balancing), so sánh metric và hiển thị timeline/Gantt cùng trạng thái queue theo thời gian.

Tính năng chính
---------------
- Nhiều thuật toán lập lịch: GLB_RR, GLB_FIFO, PAR_FIFO, CPU_Affinity, LoadBalancing, Work_Stealing
- Mô phỏng push/pull migration, migration overhead
- Dashboard Streamlit (app.py) để tương tác, cấu hình và xem timeline
- Script demo `test.py` để chạy mẫu và in kết quả

Cấu trúc dự án
---------------
- app.py: Streamlit dashboard
- test.py: script demo (in schedule steps + metrics)
- process/process.py: domain model Process, Processes
- algorithms/: các thuật toán lập lịch và Schedule base
  - schedule.py: lớp trừu tượng Schedule, tính metric cơ bản
  - schedule_step.py: ScheduleStep dataclass
  - GLB_RR.py, GLB_FIFO.py, PAR_FIFO.py, CPU_Affinity.py, load_balancing.py, work_stealing.py
- Project_summary.md, app_explain.md: tài liệu nội bộ

Yêu cầu & chạy
--------------
- Python 3.10+ (do dùng `int | None`)
- (Đề xuất) Tạo virtualenv, cài: streamlit, pandas, plotly

Chạy dashboard:

```powershell
streamlit run app.py
```

Chạy demo console:

```powershell
python test.py
```



