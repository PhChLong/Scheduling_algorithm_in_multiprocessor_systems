import algorithms

from process import Process, Processes


def add_process(ps: Processes, burst_time: int, arrival_time: int, priority: int) -> None:
    """Them 1 process vao workload test."""
    ps.add(Process(burst_time, arrival_time, priority))


def add_diverse_processes(ps: Processes) -> None:
    """Tao workload co nhieu kieu arrival/burst de so sanh algorithm ro hon.

    Gom 4 nhom:
    - mot vai job den som, burst dai de tao nen nen
    - burst job den cung luc de tao tranh chap CPU
    - nhieu job ngan xen ke de xem kha nang can bang tai
    - mot vai job den muon de xem migration/phan bo lai
    """
    # Nen dai tu som.
    add_process(ps, 32, 0, 2)
    add_process(ps, 26, 0, 4)

    # Burst den cung luc.
    add_process(ps, 8, 3, 1)
    add_process(ps, 11, 3, 3)
    add_process(ps, 5, 3, 2)

    # Nhom ngan, arrival sat nhau.
    add_process(ps, 4, 6, 5)
    add_process(ps, 6, 7, 1)
    add_process(ps, 3, 8, 4)
    add_process(ps, 7, 9, 2)
    add_process(ps, 2, 10, 5)

    # Job trung binh xen giua workload.
    add_process(ps, 14, 12, 2)
    add_process(ps, 9, 12, 3)
    add_process(ps, 18, 15, 1)
    add_process(ps, 10, 16, 4)

    # Job den muon de xem kha nang tai can bang.
    add_process(ps, 24, 25, 2)
    add_process(ps, 6, 25, 5)
    add_process(ps, 15, 28, 3)
    add_process(ps, 4, 29, 1)
    add_process(ps, 20, 35, 2)
    add_process(ps, 5, 36, 4)


def print_result(scheduler) -> None:
    print(scheduler.algorithm_name)
    for i in scheduler.steps:
        print(f"CPU {i+1}:")
        for step in scheduler.steps[i]:
            print(f"  {step}")
    print(f"CPU utilization: {scheduler.cpu_utilization:.2%}")
    print(f"Throughput: {scheduler.throughput:.4f}")
    print()


def assert_no_input_mutation() -> None:
    ps = Processes()
    add_process(ps, 5, 0, 1)
    add_process(ps, 3, 0, 1)
    original_remaining = [p.remaining_time for p in ps.all()]

    schedulers = [
        algorithms.GLB_FIFO(num_cpu=2),
        algorithms.GLB_RR(num_cpu=2, time_quantum=2),
        algorithms.PAR_FIFO(num_cpu=2),
        algorithms.CPU_Affinity(num_cpu=2, time_quantum=2, hard=True),
        algorithms.Work_Stealing(num_cpu=2, time_quantum=2),
    ]

    for scheduler in schedulers:
        scheduler.estimate(ps)
        assert [p.remaining_time for p in ps.all()] == original_remaining

    rr = algorithms.GLB_RR(num_cpu=2, time_quantum=2)
    rr.estimate(ps)
    assert all(
        step.begin_time < step.end_time
        for steps in rr.steps.values()
        for step in steps
    )


def assert_par_fifo_counts_running_load() -> None:
    ps = Processes()
    add_process(ps, 100, 0, 1)
    add_process(ps, 1, 1, 1)
    add_process(ps, 1, 1, 1)

    scheduler = algorithms.PAR_FIFO(num_cpu=2)
    scheduler.estimate(ps)

    cpu_1_steps = [(step.process_id, step.begin_time, step.end_time) for step in scheduler.steps[1]]
    assert cpu_1_steps == [(2, 1, 2), (3, 2, 3)]


def assert_final_queues_empty() -> None:
    ps = Processes()
    add_process(ps, 5, 0, 1)
    add_process(ps, 3, 1, 1)
    add_process(ps, 4, 2, 1)

    work_stealing = algorithms.Work_Stealing(num_cpu=2, time_quantum=2)
    work_stealing.estimate(ps)
    assert all(len(queue) == 0 for queue in work_stealing.local_deque.values())

    load_balancing = algorithms.LoadBalancing(num_cpu=2)
    load_balancing.estimate(ps)
    assert all(len(queue) == 0 for queue in load_balancing.cpu_queues.values())
    assert all(len(queue) == 0 for queue in load_balancing.history[-1]["queues"].values())


def run_regression_tests() -> None:
    assert_no_input_mutation()
    assert_par_fifo_counts_running_load()
    assert_final_queues_empty()



def main() -> None:
    run_regression_tests()

    ps = Processes()
    add_diverse_processes(ps)

    GLB_RR = algorithms.GLB_RR(num_cpu=4, time_quantum=15)
    GLB_RR.estimate(ps.copy())

    CPU_Affinity = algorithms.CPU_Affinity(num_cpu=4, time_quantum=5, hard=True)
    CPU_Affinity.estimate(ps.copy())

    load_balancing = algorithms.LoadBalancing(num_cpu=4)
    load_balancing.estimate(ps.copy())

    print_result(GLB_RR)
    print_result(CPU_Affinity)
    print_result(load_balancing)


if __name__ == "__main__":
    main()
