# process.py
class InvalidInputError(Exception):
    pass

class MaxProcessesError(Exception):
    pass

class ProcessNotFoundError(Exception):
    pass


class Process:
    def __init__(self, burst_time: int, arrival_time: int, priority: int):
        self._validate(burst_time, arrival_time, priority)
        self._id = None
        self._burst_time = burst_time
        self._arrival_time = arrival_time
        self._priority = priority
        self.remaining_time = burst_time

    @staticmethod
    def _validate(burst_time, arrival_time, priority):
        if burst_time <= 0:
            raise InvalidInputError("Burst time must be a positive integer")
        if arrival_time < 0:
            raise InvalidInputError("Arrival time cannot be negative")
        if priority <= 0:
            raise InvalidInputError("Priority must be a positive integer")

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def burst_time(self):
        return self._burst_time

    @burst_time.setter
    def burst_time(self, value):
        if value <= 0:
            raise InvalidInputError("Burst time must be a positive integer")
        self._burst_time = value
        self.remaining_time = value

    @property
    def arrival_time(self):
        return self._arrival_time

    @arrival_time.setter
    def arrival_time(self, value):
        if value < 0:
            raise InvalidInputError("Arrival time cannot be negative")
        self._arrival_time = value

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        if value <= 0:
            raise InvalidInputError("Priority must be a positive integer")
        self._priority = value

    def copy(self) -> "Process":
        p = Process(self._burst_time, self._arrival_time, self._priority)
        p.id = self._id
        p.remaining_time = self._burst_time
        return p

    def __repr__(self):
        return (
            f"Process(id={self._id}, burst={self._burst_time}, "
            f"arrival={self._arrival_time}, priority={self._priority})"
        )


class Processes:
    MAX = 100

    def __init__(self):
        self._list: list[Process] = []

    @property
    def count(self):
        return len(self._list)

    def add(self, p: Process):
        if self.count >= self.MAX:
            raise MaxProcessesError(f"Max {self.MAX} processes reached")
        if p is None:
            raise ValueError("Process cannot be None")
        p.id = self.count + 1
        self._list.append(p)

    def delete(self, pid: int):
        p = self.get(pid)
        self._list.remove(p)
        for i, proc in enumerate(self._list):
            proc.id = i + 1

    def modify(self, pid: int, burst_time: int, arrival_time: int, priority: int):
        p = self.get(pid)
        p.burst_time = burst_time
        p.arrival_time = arrival_time
        p.priority = priority

    def get(self, pid: int) -> Process:
        for p in self._list:
            if p.id == pid:
                return p
        raise ProcessNotFoundError(f"No process with id={pid}")

    def copy(self) -> "Processes":
        new = Processes()
        for p in self._list:
            new.add(p.copy())
        return new

    def all(self) -> list[Process]:
        return list(self._list)

    def sorted_by_arrival(self) -> list[Process]:
        return sorted(self._list, key=lambda p: (p.arrival_time, p.id))

    def sorted_by_burst(self) -> list[Process]:
        return sorted(self._list, key=lambda p: (p.burst_time, p.id))

    def sorted_by_priority(self) -> list[Process]:
        return sorted(self._list, key=lambda p: (p.priority, p.arrival_time, p.id))

    def view(self):
        for p in self._list:
            print(p)
            
    def __len__(self):
        return len(self._list)