# schedule.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from algorithms.schedule_step import ScheduleStep
from process.process import Processes, Process


@dataclass
class SystemState:
    time:        int
    cpu:         str        # "P1", "Idle", "Finished"
    ready_queue: list[str]
    color:       str


class Schedule(ABC):
    def __init__(self):
        self.algorithm_name:      str   = ""

        self.num_cpu:              int   = 0
        self.steps: dict[int, list[ScheduleStep]] = {} # {cpu_id, list_of_scheduleStep}
        
        # cập nhật bằng estimate
        self.turnaround_time:     int   = 0
        self.waiting_time:        int   = 0
        self.response_time:       int   = 0
        self.cpu_utilization:     float = 0.0
        self.throughput:          float = 0.0
        self.avg_turnaround_time: float = 0.0
        self.avg_waiting_time:    float = 0.0
        self.avg_response_time:   float = 0.0

    @abstractmethod
    def estimate(self, processes: Processes) -> None: ...

    def _update_basic_metrics(self, process_count: int) -> None:
        total_time = max(
            (step.end_time for steps in self.steps.values() for step in steps),
            default=0,
        )
        busy_time = sum(
            step.end_time - step.begin_time
            for steps in self.steps.values()
            for step in steps
        )
        self.cpu_utilization = 0.0 if total_time == 0 else busy_time / (self.num_cpu * total_time)
        self.throughput = 0.0 if total_time == 0 else process_count / total_time
