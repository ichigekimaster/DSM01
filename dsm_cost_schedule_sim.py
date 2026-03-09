#!/usr/bin/env python3
"""DSM ベースのコスト・期間リスクシミュレーション（CLI + GUI）。"""

from __future__ import annotations

import argparse
import csv
import json
import random
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Tuple


@dataclass
class SimulationConfig:
    num_trials: int = 1000
    max_iterations: int = 50
    random_seed: int = 42


@dataclass
class TaskSet:
    names: List[str]
    base_cost: List[float]
    base_duration: List[float]
    cost_stddev: List[float]
    duration_stddev: List[float]


def _to_float(value: str, column: str, row_idx: int) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError(f"tasks CSV の {column} が空欄です（行 {row_idx + 2}）")
    return float(value)


def load_tasks(path: Path) -> TaskSet:
    required = {
        "task_name",
        "base_cost",
        "base_duration",
        "cost_stddev",
        "duration_stddev",
    }

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("tasks CSV にヘッダーがありません。")
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"tasks CSV に必須列がありません: {sorted(missing)}")

        names, base_cost, base_duration, cost_stddev, duration_stddev = [], [], [], [], []

        for idx, row in enumerate(reader):
            name = (row.get("task_name") or "").strip()
            if not name:
                raise ValueError(f"task_name が空欄です（行 {idx + 2}）")

            names.append(name)
            base_cost.append(_to_float(row.get("base_cost", ""), "base_cost", idx))
            base_duration.append(
                _to_float(row.get("base_duration", ""), "base_duration", idx)
            )
            cost_stddev.append(_to_float(row.get("cost_stddev", ""), "cost_stddev", idx))
            duration_stddev.append(
                _to_float(row.get("duration_stddev", ""), "duration_stddev", idx)
            )

    if not names:
        raise ValueError("tasks CSV が空です。")

    return TaskSet(names, base_cost, base_duration, cost_stddev, duration_stddev)


def load_dsm(path: Path, n_tasks: int) -> List[List[float]]:
    matrix: List[List[float]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for r_idx, row in enumerate(reader):
            if len(row) != n_tasks:
                raise ValueError(
                    f"DSM列数が不正です（行 {r_idx + 1}）: {len(row)} != {n_tasks}"
                )
            vals = []
            for c_idx, cell in enumerate(row):
                if str(cell).strip() == "":
                    raise ValueError(
                        f"DSM行列に空欄があります（行 {r_idx + 1}, 列 {c_idx + 1}）"
                    )
                v = float(cell)
                if not (0.0 <= v <= 1.0):
                    raise ValueError("DSMの値は 0.0〜1.0 で入力してください。")
                vals.append(v)
            matrix.append(vals)

    if len(matrix) != n_tasks:
        raise ValueError(f"DSM行数が不正です: {len(matrix)} != {n_tasks}")

    for i in range(n_tasks):
        matrix[i][i] = 0.0

    return matrix


def load_config(path: Path) -> SimulationConfig:
    if not path.exists():
        return SimulationConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return SimulationConfig(
        num_trials=int(raw.get("num_trials", 1000)),
        max_iterations=int(raw.get("max_iterations", 50)),
        random_seed=int(raw.get("random_seed", 42)),
    )


def _sample_positive(rng: random.Random, mean: float, std: float) -> float:
    if std <= 0:
        return max(mean, 0.0)
    return max(rng.gauss(mean, std), 0.0)


def run_trial(
    rng: random.Random,
    tasks: TaskSet,
    dsm: List[List[float]],
    max_iterations: int,
) -> Tuple[float, float]:
    n = len(tasks.names)
    needs_execution = [True] * n
    total_cost = 0.0
    total_duration = 0.0

    for _ in range(max_iterations):
        if not any(needs_execution):
            break

        next_needs = [False] * n

        for i in range(n):
            if not needs_execution[i]:
                continue

            total_cost += _sample_positive(rng, tasks.base_cost[i], tasks.cost_stddev[i])
            total_duration += _sample_positive(
                rng, tasks.base_duration[i], tasks.duration_stddev[i]
            )

            for j in range(n):
                if i == j:
                    continue
                if rng.random() < dsm[i][j]:
                    next_needs[j] = True

        needs_execution = next_needs

    return total_cost, total_duration


def run_simulation(
    tasks: TaskSet, dsm: List[List[float]], cfg: SimulationConfig
) -> List[Tuple[float, float]]:
    rng = random.Random(cfg.random_seed)
    return [run_trial(rng, tasks, dsm, cfg.max_iterations) for _ in range(cfg.num_trials)]


def save_results_csv(results: List[Tuple[float, float]], out_csv: Path) -> None:
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["total_cost", "total_duration"])
        writer.writerows(results)


def save_scatter_svg(results: List[Tuple[float, float]], out_svg: Path) -> None:
    width, height = 900, 650
    margin_l, margin_r, margin_t, margin_b = 90, 40, 40, 80
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    xs = [p[0] for p in results]
    ys = [p[1] for p in results]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    if min_x == max_x:
        max_x += 1.0
    if min_y == max_y:
        max_y += 1.0

    def x_to_px(x: float) -> float:
        return margin_l + (x - min_x) / (max_x - min_x) * plot_w

    def y_to_px(y: float) -> float:
        return margin_t + plot_h - (y - min_y) / (max_y - min_y) * plot_h

    circles = []
    for x, y in results:
        circles.append(
            f'<circle cx="{x_to_px(x):.2f}" cy="{y_to_px(y):.2f}" r="3" fill="#1f77b4" fill-opacity="0.45" />'
        )

    svg = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\">
  <rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" fill=\"white\" />
  <text x=\"{width/2:.0f}\" y=\"24\" text-anchor=\"middle\" font-size=\"20\" font-family=\"sans-serif\">DSM Monte Carlo Simulation: Cost vs Schedule</text>
  <line x1=\"{margin_l}\" y1=\"{margin_t + plot_h}\" x2=\"{margin_l + plot_w}\" y2=\"{margin_t + plot_h}\" stroke=\"#333\" stroke-width=\"2\" />
  <line x1=\"{margin_l}\" y1=\"{margin_t}\" x2=\"{margin_l}\" y2=\"{margin_t + plot_h}\" stroke=\"#333\" stroke-width=\"2\" />
  <text x=\"{margin_l + plot_w/2:.0f}\" y=\"{height - 20}\" text-anchor=\"middle\" font-size=\"16\" font-family=\"sans-serif\">Total Cost</text>
  <text x=\"24\" y=\"{margin_t + plot_h/2:.0f}\" text-anchor=\"middle\" transform=\"rotate(-90 24 {margin_t + plot_h/2:.0f})\" font-size=\"16\" font-family=\"sans-serif\">Total Duration</text>
  <text x=\"{margin_l}\" y=\"{margin_t + plot_h + 24}\" font-size=\"12\" font-family=\"sans-serif\">{min_x:.2f}</text>
  <text x=\"{margin_l + plot_w}\" y=\"{margin_t + plot_h + 24}\" text-anchor=\"end\" font-size=\"12\" font-family=\"sans-serif\">{max_x:.2f}</text>
  <text x=\"{margin_l - 8}\" y=\"{margin_t + plot_h}\" text-anchor=\"end\" font-size=\"12\" font-family=\"sans-serif\">{min_y:.2f}</text>
  <text x=\"{margin_l - 8}\" y=\"{margin_t + 4}\" text-anchor=\"end\" font-size=\"12\" font-family=\"sans-serif\">{max_y:.2f}</text>
  {''.join(circles)}
</svg>
"""
    out_svg.write_text(svg, encoding="utf-8")


def create_templates(out_dir: Path, num_tasks: int = 5) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "tasks_template.csv").open("w", encoding="utf-8", newline="") as f:
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
        for i in range(num_tasks):
            writer.writerow([f"Task{i+1}", "", "", "", ""])

    with (out_dir / "dsm_template.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for _ in range(num_tasks):
            writer.writerow([0.0] * num_tasks)

    config = {"num_trials": 1000, "max_iterations": 50, "random_seed": 42}
    (out_dir / "config_template.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_windows_launcher(desktop_dir: Path, project_dir: Path) -> Path:
    """Win11向けのダブルクリック起動バッチファイルを作成する。"""
    desktop_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = desktop_dir / "DSM_Cost_Schedule_Simulator.bat"

    project_dir_win = str(project_dir).replace("/", "\\")
    launcher_text = (
        "@echo off\n"
        "setlocal\n"
        f'cd /d "{project_dir_win}"\n'
        "python dsm_cost_schedule_sim.py --gui\n"
        "if errorlevel 1 (\n"
        "  echo.\n"
        "  echo 起動に失敗しました。Pythonのインストールとパス設定を確認してください。\n"
        "  pause\n"
        ")\n"
        "endlocal\n"
    )
    launcher_path.write_text(launcher_text, encoding="utf-8")
    return launcher_path


class SimulatorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("DSM Cost/Schedule Simulator")
        self.root.geometry("980x740")

        self.num_tasks_var = tk.IntVar(value=5)
        self.num_trials_var = tk.IntVar(value=1000)
        self.max_iter_var = tk.IntVar(value=50)
        self.seed_var = tk.IntVar(value=42)

        self.task_entries: List[dict[str, tk.Entry]] = []
        self.dsm_entries: List[List[tk.Entry]] = []

        self._build_ui()
        self._rebuild_tables()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="タスク数").pack(side="left")
        ttk.Spinbox(top, from_=2, to=30, textvariable=self.num_tasks_var, width=5).pack(side="left", padx=4)
        ttk.Button(top, text="表を再作成", command=self._rebuild_tables).pack(side="left", padx=6)

        ttk.Label(top, text="試行回数").pack(side="left", padx=(20, 0))
        ttk.Entry(top, textvariable=self.num_trials_var, width=8).pack(side="left", padx=4)
        ttk.Label(top, text="反復上限").pack(side="left")
        ttk.Entry(top, textvariable=self.max_iter_var, width=6).pack(side="left", padx=4)
        ttk.Label(top, text="seed").pack(side="left")
        ttk.Entry(top, textvariable=self.seed_var, width=8).pack(side="left", padx=4)

        pane = ttk.PanedWindow(self.root, orient="vertical")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        self.tasks_frame = ttk.Labelframe(pane, text="Tasks 入力")
        self.dsm_frame = ttk.Labelframe(pane, text="DSM 入力 (0〜1)")
        pane.add(self.tasks_frame, weight=1)
        pane.add(self.dsm_frame, weight=2)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="CSVへ保存", command=self.save_inputs).pack(side="left")
        ttk.Button(bottom, text="CSV読込", command=self.load_inputs).pack(side="left", padx=6)
        ttk.Button(bottom, text="シミュレーション実行", command=self.run).pack(side="right")

    def _clear_frame(self, frame: ttk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _rebuild_tables(self) -> None:
        n = int(self.num_tasks_var.get())
        self.task_entries = []
        self.dsm_entries = []
        self._clear_frame(self.tasks_frame)
        self._clear_frame(self.dsm_frame)

        headers = ["task_name", "base_cost", "base_duration", "cost_stddev", "duration_stddev"]
        for c, h in enumerate(headers):
            ttk.Label(self.tasks_frame, text=h).grid(row=0, column=c, padx=2, pady=2)

        for r in range(n):
            row_entries: dict[str, tk.Entry] = {}
            defaults = [f"Task{r+1}", "", "", "", ""]
            for c, key in enumerate(headers):
                e = ttk.Entry(self.tasks_frame, width=14)
                e.grid(row=r + 1, column=c, padx=2, pady=1)
                e.insert(0, defaults[c])
                row_entries[key] = e
            self.task_entries.append(row_entries)

        for c in range(n):
            ttk.Label(self.dsm_frame, text=str(c + 1)).grid(row=0, column=c + 1, padx=1, pady=1)
        for r in range(n):
            ttk.Label(self.dsm_frame, text=str(r + 1)).grid(row=r + 1, column=0, padx=1, pady=1)
            row = []
            for c in range(n):
                e = ttk.Entry(self.dsm_frame, width=5)
                e.grid(row=r + 1, column=c + 1, padx=1, pady=1)
                e.insert(0, "0.0")
                row.append(e)
            self.dsm_entries.append(row)

    def _collect_taskset(self) -> TaskSet:
        names, bc, bd, cs, ds = [], [], [], [], []
        for i, row in enumerate(self.task_entries):
            name = row["task_name"].get().strip()
            if not name:
                raise ValueError(f"task_name が空欄です（行 {i+1}）")
            names.append(name)
            bc.append(float(row["base_cost"].get()))
            bd.append(float(row["base_duration"].get()))
            cs.append(float(row["cost_stddev"].get()))
            ds.append(float(row["duration_stddev"].get()))
        return TaskSet(names, bc, bd, cs, ds)

    def _collect_dsm(self) -> List[List[float]]:
        n = len(self.dsm_entries)
        out: List[List[float]] = []
        for r in range(n):
            row = []
            for c in range(n):
                v = float(self.dsm_entries[r][c].get())
                if not (0 <= v <= 1):
                    raise ValueError("DSMの値は0〜1で入力してください")
                row.append(v)
            row[r] = 0.0
            out.append(row)
        return out

    def save_inputs(self) -> None:
        try:
            out_dir = Path(filedialog.askdirectory(title="保存先フォルダを選択"))
            if not str(out_dir):
                return
            out_dir.mkdir(parents=True, exist_ok=True)

            taskset = self._collect_taskset()
            with (out_dir / "tasks_template.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["task_name", "base_cost", "base_duration", "cost_stddev", "duration_stddev"])
                for i in range(len(taskset.names)):
                    w.writerow([taskset.names[i], taskset.base_cost[i], taskset.base_duration[i], taskset.cost_stddev[i], taskset.duration_stddev[i]])

            dsm = self._collect_dsm()
            with (out_dir / "dsm_template.csv").open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows(dsm)

            cfg = {
                "num_trials": int(self.num_trials_var.get()),
                "max_iterations": int(self.max_iter_var.get()),
                "random_seed": int(self.seed_var.get()),
            }
            (out_dir / "config_template.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("保存完了", f"入力データを保存しました:\n{out_dir}")
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def load_inputs(self) -> None:
        try:
            tasks_path = filedialog.askopenfilename(title="tasks CSVを選択", filetypes=[("CSV", "*.csv")])
            if not tasks_path:
                return
            dsm_path = filedialog.askopenfilename(title="DSM CSVを選択", filetypes=[("CSV", "*.csv")])
            if not dsm_path:
                return

            taskset = load_tasks(Path(tasks_path))
            dsm = load_dsm(Path(dsm_path), len(taskset.names))

            self.num_tasks_var.set(len(taskset.names))
            self._rebuild_tables()

            for i, name in enumerate(taskset.names):
                self.task_entries[i]["task_name"].delete(0, tk.END)
                self.task_entries[i]["task_name"].insert(0, name)
                self.task_entries[i]["base_cost"].delete(0, tk.END)
                self.task_entries[i]["base_cost"].insert(0, str(taskset.base_cost[i]))
                self.task_entries[i]["base_duration"].delete(0, tk.END)
                self.task_entries[i]["base_duration"].insert(0, str(taskset.base_duration[i]))
                self.task_entries[i]["cost_stddev"].delete(0, tk.END)
                self.task_entries[i]["cost_stddev"].insert(0, str(taskset.cost_stddev[i]))
                self.task_entries[i]["duration_stddev"].delete(0, tk.END)
                self.task_entries[i]["duration_stddev"].insert(0, str(taskset.duration_stddev[i]))

            for r in range(len(dsm)):
                for c in range(len(dsm)):
                    self.dsm_entries[r][c].delete(0, tk.END)
                    self.dsm_entries[r][c].insert(0, str(dsm[r][c]))

            cfg_path = Path(tasks_path).with_name("config_template.json")
            if cfg_path.exists():
                cfg = load_config(cfg_path)
                self.num_trials_var.set(cfg.num_trials)
                self.max_iter_var.set(cfg.max_iterations)
                self.seed_var.set(cfg.random_seed)

            messagebox.showinfo("読込完了", "CSVを読み込みました。")
        except Exception as e:
            messagebox.showerror("エラー", str(e))

    def run(self) -> None:
        try:
            taskset = self._collect_taskset()
            dsm = self._collect_dsm()
            cfg = SimulationConfig(
                num_trials=int(self.num_trials_var.get()),
                max_iterations=int(self.max_iter_var.get()),
                random_seed=int(self.seed_var.get()),
            )
            out_dir = Path(filedialog.askdirectory(title="結果出力フォルダを選択"))
            if not str(out_dir):
                return
            out_dir.mkdir(parents=True, exist_ok=True)

            results = run_simulation(taskset, dsm, cfg)
            save_results_csv(results, out_dir / "simulation_results.csv")
            save_scatter_svg(results, out_dir / "cost_duration_scatter.svg")
            messagebox.showinfo(
                "シミュレーション完了",
                f"試行数: {len(results)}\n保存先: {out_dir}\n出力: simulation_results.csv / cost_duration_scatter.svg",
            )
        except Exception as e:
            messagebox.showerror("エラー", str(e))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DSMコスト・期間リスクシミュレーション")
    p.add_argument("--tasks", type=Path, help="tasks CSV")
    p.add_argument("--dsm", type=Path, help="DSM CSV")
    p.add_argument("--config", type=Path, default=Path("config.json"), help="config JSON")
    p.add_argument("--out-csv", type=Path, default=Path("simulation_results.csv"))
    p.add_argument("--out-svg", type=Path, default=Path("cost_duration_scatter.svg"))
    p.add_argument("--create-templates", action="store_true")
    p.add_argument("--template-dir", type=Path, default=Path("templates"))
    p.add_argument("--template-tasks", type=int, default=5)
    p.add_argument(
        "--create-win-launcher",
        action="store_true",
        help="Windows用デスクトップ起動バッチ(.bat)を作成する",
    )
    p.add_argument(
        "--win-desktop-dir",
        type=Path,
        default=Path.home() / "Desktop",
        help="Windowsデスクトップフォルダ（既定: ~/Desktop）",
    )
    p.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="起動時に移動するプロジェクトフォルダ（既定: カレントディレクトリ）",
    )
    p.add_argument("--gui", action="store_true", help="GUIモードで起動")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.gui or (not args.create_templates and not args.tasks and not args.dsm):
        root = tk.Tk()
        SimulatorGUI(root)
        root.mainloop()
        return

    if args.create_templates:
        create_templates(args.template_dir, args.template_tasks)
        print(f"テンプレートを作成しました: {args.template_dir}")
        return

    if args.create_win_launcher:
        out = create_windows_launcher(args.win_desktop_dir, args.project_dir)
        print(f"Windows起動ファイルを作成しました: {out}")
        return

    if not args.tasks or not args.dsm:
        raise SystemExit("--tasks と --dsm を指定してください。")

    tasks = load_tasks(args.tasks)
    dsm = load_dsm(args.dsm, len(tasks.names))
    cfg = load_config(args.config)

    results = run_simulation(tasks, dsm, cfg)
    save_results_csv(results, args.out_csv)
    save_scatter_svg(results, args.out_svg)

    print(f"シミュレーション完了: {len(results)} 試行")
    print(f"CSV: {args.out_csv}")
    print(f"散布図(SVG): {args.out_svg}")


if __name__ == "__main__":
    main()

