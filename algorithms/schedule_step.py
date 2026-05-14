from dataclasses import dataclass

@dataclass
class ScheduleStep:
    process_id: int
    begin_time: int
    end_time:   int

    def __repr__(self):
        return f"ScheduleStep(pid={self.process_id}, begin={self.begin_time}, end={self.end_time})"