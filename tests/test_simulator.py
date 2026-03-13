import csv
from pathlib import Path

from dsm_cost_schedule_sim import (
    SimulationConfig,
    create_windows_launcher,
    create_windows_start_files,
    load_dsm,
    load_tasks,
    run_simulation,
    save_results_csv,
    save_scatter_svg,
)


def test_run_simulation_end_to_end(tmp_path: Path) -> None:
    tasks_path = tmp_path / "tasks.csv"
    dsm_path = tmp_path / "dsm.csv"
    out_csv = tmp_path / "out.csv"
    out_svg = tmp_path / "plot.svg"

    with tasks_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "task_name",
                "base_cost",
                "base_duration",
                "cost_stddev",
                "duration_stddev",
            ]
        )
        writer.writerow(["A", 10, 1, 1, 0.2])
        writer.writerow(["B", 20, 2, 1, 0.2])
        writer.writerow(["C", 30, 3, 1, 0.2])

    with dsm_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([0.0, 0.1, 0.0])
        writer.writerow([0.2, 0.0, 0.1])
        writer.writerow([0.0, 0.2, 0.0])

    tasks = load_tasks(tasks_path)
    dsm = load_dsm(dsm_path, n_tasks=3)
    cfg = SimulationConfig(num_trials=100, max_iterations=20, random_seed=123)

    result = run_simulation(tasks, dsm, cfg)

    assert len(result) == 100
    assert all(c >= 0 for c, _ in result)
    assert all(d >= 0 for _, d in result)

    save_results_csv(result, out_csv)
    save_scatter_svg(result, out_svg)

    assert out_csv.exists()
    assert out_svg.exists()


def test_create_windows_launcher(tmp_path: Path) -> None:
    desktop = tmp_path / "Desktop"
    project = Path("C:/Users/user/DSM01")
    launcher = create_windows_launcher(desktop, project)

    assert launcher.exists()
    text = launcher.read_text(encoding="utf-8")
    assert "DSM_Cost_Schedule_Simulator.bat" in str(launcher)
    assert "dsm_cost_schedule_sim.py --gui" in text
    assert "set \"DIR=" in text
    assert "where py" in text
    assert "DSM_LAUNCHER_VERSION=5" in text


def test_create_windows_start_files(tmp_path: Path) -> None:
    ps1, bat = create_windows_start_files(tmp_path)

    assert ps1.exists()
    assert bat.exists()
    assert "dsm_cost_schedule_sim.py" in ps1.read_text(encoding="utf-8")
    assert "git pull --ff-only" in ps1.read_text(encoding="utf-8")
    assert "start_latest_windows.ps1" in bat.read_text(encoding="utf-8")
