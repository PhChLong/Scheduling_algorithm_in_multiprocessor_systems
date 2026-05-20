from .schedule import Schedule
from .schedule_step import ScheduleStep
from process.process import Process, Processes


class LoadBalancing(Schedule):
    """Scheduler mo phong can bang tai tren nhieu CPU.

    Moi CPU co mot queue FIFO rieng.
    Process moi se duoc dua vao CPU co tong tai nho nhat.
    Trong luc chay, thuat toan co 2 kieu migration:
    - push: CPU ban nhat day bot viec sang CPU ranh nhat
    - pull: CPU dang idle di "keo" viec tu CPU ban nhat
    """

    def __init__(self, num_cpu: int = 4, threshold: int = 2, migration_overhead: int = 1):
        super().__init__()
        self.algorithm_name = "Load Balancing"
        self.num_cpu = num_cpu
        self.threshold = threshold
        self.migration_overhead = migration_overhead
        self.cpu_queues = {i: [] for i in range(num_cpu)}
        self._history: list[dict] = []

    def _reset(self):
        """Reset toan bo trang thai mo phong truoc khi estimate bo process moi."""
        self.steps = {i: [] for i in range(self.num_cpu)}
        self.cpu_queues = {i: [] for i in range(self.num_cpu)}
        self._history = []

    def _normalize_processes(self, processes: Processes) -> list[Process]:
        """Copy roi sort process theo arrival time.

        Ham nay tranh sua truc tiep input vi trong luc mo phong
        `remaining_time` se bi giam dan.
        """
        return [p.copy() for p in processes.sorted_by_arrival()]

    def _cpu_load(self, cpu_id: int) -> int:
        """Tinh tong remaining_time cua toan bo queue tren mot CPU."""
        return sum(process.remaining_time for process in self.cpu_queues[cpu_id])

    def _least_loaded_cpu(self) -> int:
        """Tra ve CPU co tai nho nhat.

        Tie-break:
        1. tong tai nho hon
        2. so process trong queue it hon
        3. id CPU nho hon
        """
        return min(
            range(self.num_cpu),
            key=lambda cpu_id: (self._cpu_load(cpu_id), len(self.cpu_queues[cpu_id]), cpu_id),
        )

    def _busiest_cpu(self, exclude: int | None = None) -> int | None:
        """Tra ve CPU ban nhat, co the bo qua mot CPU neu can."""
        candidates = [cpu_id for cpu_id in range(self.num_cpu) if cpu_id != exclude]
        if not candidates:
            return None
        cpu_id = max(candidates, key=lambda idx: (self._cpu_load(idx), len(self.cpu_queues[idx]), -idx))
        if self._cpu_load(cpu_id) == 0:
            return None
        return cpu_id

    def _append_step(self, cpu_id: int, process_id: int, begin_time: int, end_time: int):
        """Ghi mot doan thuc thi vao ket qua schedule.

        Neu cung process tiep tuc chay lien mach tren cung CPU thi gop lai
        thanh 1 step de output gon hon.
        """
        if begin_time >= end_time:
            return
        steps = self.steps[cpu_id]
        if steps and steps[-1].process_id == process_id and steps[-1].end_time == begin_time:
            steps[-1].end_time = end_time
            return
        steps.append(ScheduleStep(process_id, begin_time, end_time, cpu_id))

    def _record_state(self, current_time: int):
        """Luu snapshot queue/load tai moi moc thoi gian de debug hoac ve UI."""
        self._history.append(
            {
                "time": current_time,
                "queues": {
                    cpu_id: [process.id for process in queue]
                    for cpu_id, queue in self.cpu_queues.items()
                },
                "loads": {
                    cpu_id: self._cpu_load(cpu_id)
                    for cpu_id in range(self.num_cpu)
                },
            }
        )

    def _assign_new_arrivals(self, processes: list[Process], next_index: int, current_time: int) -> int:
        """Dua cac process da den vao CPU co tai nho nhat tai thoi diem hien tai."""
        while next_index < len(processes) and processes[next_index].arrival_time <= current_time:
            target_cpu = self._least_loaded_cpu()
            self.cpu_queues[target_cpu].append(processes[next_index])
            next_index += 1
        return next_index

    def _migrate(self, source_cpu_id: int, target_cpu_id: int) -> bool:
        """Chuyen mot process dang cho tu source sang target.

        Queue dang duoc xu ly theo FIFO nen process dang chay o index 0
        khong bi di chuyen. Ham nay lay process cuoi queue de migrate.
        Moi lan migrate se cong them `migration_overhead` vao remaining time.
        """
        source_queue = self.cpu_queues[source_cpu_id]
        if len(source_queue) <= 1:
            return False

        migrated_process = source_queue.pop()
        migrated_process.remaining_time += self.migration_overhead
        self.cpu_queues[target_cpu_id].append(migrated_process)
        return True

    def _migration_reduces_imbalance(self, source_cpu_id: int, target_cpu_id: int) -> bool:
        """Chi migrate neu load gap sau khi chuyen se nho hon truoc do."""
        source_queue = self.cpu_queues[source_cpu_id]
        if len(source_queue) <= 1:
            return False

        moved_process = source_queue[-1]
        source_load = self._cpu_load(source_cpu_id)
        target_load = self._cpu_load(target_cpu_id)
        current_gap = abs(source_load - target_load)
        new_gap = abs(
            (source_load - moved_process.remaining_time)
            - (target_load + moved_process.remaining_time + self.migration_overhead)
        )
        return new_gap < current_gap

    def push_migration(self):
        """CPU ban nhat chu dong day viec sang CPU ranh nhat.

        Lap lai cho den khi:
        - chenhlech load <= threshold, hoac
        - migrate khong con giup can bang hon, hoac
        - khong con process hop le de migrate.
        """
        while True:
            busiest_cpu_id = self._busiest_cpu()
            idlest_cpu_id = self._least_loaded_cpu()

            if busiest_cpu_id is None or busiest_cpu_id == idlest_cpu_id:
                return

            if self._cpu_load(busiest_cpu_id) - self._cpu_load(idlest_cpu_id) <= self.threshold:
                return

            if not self._migration_reduces_imbalance(busiest_cpu_id, idlest_cpu_id):
                return

            if not self._migrate(busiest_cpu_id, idlest_cpu_id):
                return

    def pull_migration(self, idle_cpu_id):
        """Neu mot CPU dang idle, no thu lay viec tu CPU ban nhat."""
        if self.cpu_queues[idle_cpu_id]:
            return False

        donor_cpu_id = self._busiest_cpu(exclude=idle_cpu_id)
        if donor_cpu_id is None:
            return False

        if self._cpu_load(donor_cpu_id) - self._cpu_load(idle_cpu_id) <= 0:
            return False

        if not self._migration_reduces_imbalance(donor_cpu_id, idle_cpu_id):
            return False

        return self._migrate(donor_cpu_id, idle_cpu_id)

    def estimate(self, process: Processes):
        """Chay toan bo mo phong va tra ve cac step da duoc schedule.

        Moi vong lap thoi gian se lam 6 buoc:
        1. Dua process moi den vao queue
        2. Thu push migration de can bang toan cuc
        3. Cho CPU idle thu pull migration
        4. Luu lai state hien tai
        5. Moi CPU dang co viec chay 1 tick
        6. Loai process vua hoan thanh ra khoi queue

        Cuoi cung tinh them:
        - cpu_utilization = so CPU-tick co lam viec / tong CPU-tick
        - throughput = tong so process / tong thoi gian mo phong
        """
        self._reset()
        processes = self._normalize_processes(process)
        total_processes = len(processes)

        current_time = 0
        next_process_index = 0
        completed_processes = 0
        busy_ticks = 0

        while completed_processes < total_processes:
            # Dua tat ca process da arrival vao queue tai current_time.
            next_process_index = self._assign_new_arrivals(processes, next_process_index, current_time)

            # Rebalance truoc khi CPU chay tick hien tai.
            self.push_migration()

            for cpu_id in range(self.num_cpu):
                # CPU nao dang rong thi thu "keo" viec tu CPU ban hon.
                if not self.cpu_queues[cpu_id]:
                    self.pull_migration(cpu_id)

            self._record_state(current_time)

            active_cpus = [cpu_id for cpu_id in range(self.num_cpu) if self.cpu_queues[cpu_id]]
            if not active_cpus:
                # Neu chua co viec nao san sang chay, nhay toi thoi diem process tiep theo den.
                if next_process_index < total_processes:
                    current_time = processes[next_process_index].arrival_time
                    continue
                break

            for cpu_id in active_cpus:
                # FIFO: process dau queue la process dang duoc CPU xu ly.
                running_process = self.cpu_queues[cpu_id][0]
                running_process.remaining_time -= 1
                self._append_step(cpu_id, running_process.id, current_time, current_time + 1)
                busy_ticks += 1

            current_time += 1

            for cpu_id in active_cpus:
                # Sau khi chay xong 1 tick, process nao het time thi remove khoi queue.
                running_process = self.cpu_queues[cpu_id][0]
                if running_process.remaining_time <= 0:
                    self.cpu_queues[cpu_id].pop(0)
                    completed_processes += 1

        total_time = current_time
        self.cpu_utilization = 0.0 if total_time == 0 else busy_ticks / (self.num_cpu * total_time)
        self.throughput = 0.0 if total_time == 0 else total_processes / total_time
        return self.steps
