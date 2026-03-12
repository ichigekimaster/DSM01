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

LAUNCHER_SCRIPT_VERSION = 4
GUI_LAYOUT_VERSION = "DSM-20x20"
GUI_WINDOW_TITLE = "DSM Cost/Schedule Simulator + DSM Viewer"


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

    project_dir = project_dir.resolve()
    escaped_project_dir = str(project_dir).replace("\\", "\\\\")
    launcher_text = f"""@echo off
setlocal
REM DSM_LAUNCHER_VERSION=5
set "DIR={escaped_project_dir}"
if not exist "%DIR%\dsm_cost_schedule_sim.py" (
  echo dsm_cost_schedule_sim.py not found in: %DIR%
  pause
  exit /b 1
)
cd /d "%DIR%"
echo Launching from: %DIR%
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 dsm_cost_schedule_sim.py --gui
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python dsm_cost_schedule_sim.py --gui
  ) else (
    echo Python is not installed or PATH is not set.
    pause
    exit /b 1
  )
)
if errorlevel 1 (
  echo.
  echo Launch failed. Run in PowerShell: python "%DIR%\dsm_cost_schedule_sim.py" --gui
  pause
)
endlocal
"""
    launcher_path.write_text(launcher_text, encoding="ascii")
    return launcher_path


def create_windows_start_files(project_dir: Path) -> tuple[Path, Path]:
    """Windows向けのワンクリック起動ファイル2点を作成する。"""
    project_dir = project_dir.resolve()
    ps1_path = project_dir / "start_latest_windows.ps1"
    bat_path = project_dir / "START_LATEST_DSM.bat"

    escaped_project_dir = str(project_dir).replace("\\", "\\\\")
    ps1_text = f'''$ErrorActionPreference = "Stop"

$ProjectDir = "{escaped_project_dir}"
Set-Location $ProjectDir

if ((Test-Path (Join-Path $ProjectDir '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {{
  Write-Host "Updating from Git..."
  try {{
    git pull --ff-only | Out-Host
  }} catch {{
    Write-Host "Git update failed. Continue with local files."
  }}
}}

if (-not (Test-Path (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py'))) {{
  Write-Host "dsm_cost_schedule_sim.py が見つかりません: $ProjectDir"
  pause
  exit 1
}}

Write-Host "Launching latest GUI from: $ProjectDir"

$ok = $false
try {{
  & py -3 (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py') --gui
  if ($LASTEXITCODE -eq 0) {{ $ok = $true }}
}} catch {{}}

if (-not $ok) {{
  & python (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py') --gui
  if ($LASTEXITCODE -eq 0) {{ $ok = $true }}
}}

if (-not $ok) {{
  Write-Host "Launch failed. Run in PowerShell: python dsm_cost_schedule_sim.py --gui"
  pause
  exit 1
}}
'''

    bat_text = """@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_latest_windows.ps1"
if errorlevel 1 (
  echo.
  echo Failed to refresh/start launcher.
  pause
)
endlocal
"""

    ps1_path.write_text(ps1_text, encoding="utf-8")
    bat_path.write_text(bat_text, encoding="ascii")
    return ps1_path, bat_path



class SimulatorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(GUI_WINDOW_TITLE)
        self.root.geometry("980x740")

        self.num_tasks_var = tk.IntVar(value=20)
        self.num_trials_var = tk.IntVar(value=1000)
        self.max_iter_var = tk.IntVar(value=50)
        self.seed_var = tk.IntVar(value=42)

        self.task_entries: List[dict[str, tk.Entry]] = []
        self.dsm_entries: List[List[tk.Widget]] = []
        self.col_header_labels: List[ttk.Label] = []
        self.row_header_labels: List[ttk.Label] = []
        self.visual_canvas: tk.Canvas | None = None
        self.visual_order: List[int] = []
        self.use_reordered_view = False

        self._build_ui()
        self._rebuild_tables()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_cost = ttk.Frame(notebook)
        self.tab_dsm_input = ttk.Frame(notebook)
        self.tab_dsm_visual = ttk.Frame(notebook)
        notebook.add(self.tab_cost, text="コスト・スケジュール")
        notebook.add(self.tab_dsm_input, text="DSM入力")
        notebook.add(self.tab_dsm_visual, text="DSM可視化")

        cfg = ttk.Frame(self.tab_cost, padding=8)
        cfg.pack(fill="x")
        ttk.Label(cfg, text="試行回数").pack(side="left")
        ttk.Entry(cfg, textvariable=self.num_trials_var, width=8).pack(side="left", padx=4)
        ttk.Label(cfg, text="反復上限").pack(side="left")
        ttk.Entry(cfg, textvariable=self.max_iter_var, width=6).pack(side="left", padx=4)
        ttk.Label(cfg, text="seed").pack(side="left")
        ttk.Entry(cfg, textvariable=self.seed_var, width=8).pack(side="left", padx=4)

        self.tasks_frame = ttk.Labelframe(self.tab_cost, text="Tasks 入力", padding=6)
        self.tasks_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cost_bottom = ttk.Frame(self.tab_cost, padding=8)
        cost_bottom.pack(fill="x")
        ttk.Button(cost_bottom, text="CSVへ保存", command=self.save_inputs).pack(side="left")
        ttk.Button(cost_bottom, text="CSV読込", command=self.load_inputs).pack(side="left", padx=6)
        ttk.Button(cost_bottom, text="シミュレーション実行", command=self.run).pack(side="right")

        dsm_top = ttk.Frame(self.tab_dsm_input, padding=8)
        dsm_top.pack(fill="x")
        ttk.Label(dsm_top, text="行列サイズ").pack(side="left")
        ttk.Spinbox(dsm_top, from_=2, to=30, textvariable=self.num_tasks_var, width=5).pack(side="left", padx=4)
        ttk.Button(dsm_top, text="－", width=3, command=self._decrease_tasks).pack(side="left", padx=(4, 1))
        ttk.Button(dsm_top, text="＋", width=3, command=self._increase_tasks).pack(side="left", padx=(1, 6))
        ttk.Button(dsm_top, text="表を再作成", command=self._rebuild_tables).pack(side="left", padx=6)

        self.dsm_input_frame = ttk.Labelframe(self.tab_dsm_input, text="DSM 入力 (0〜1)", padding=6)
        self.dsm_input_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.dsm_visual_frame = ttk.Labelframe(self.tab_dsm_visual, text="DSM可視化パネル", padding=6)
        self.dsm_visual_frame.pack(fill="both", expand=True, padx=8, pady=8)

    def _clear_frame(self, frame: ttk.Frame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _increase_tasks(self) -> None:
        self.num_tasks_var.set(min(int(self.num_tasks_var.get()) + 1, 30))
        self._rebuild_tables()

    def _decrease_tasks(self) -> None:
        self.num_tasks_var.set(max(int(self.num_tasks_var.get()) - 1, 2))
        self._rebuild_tables()

    @staticmethod
    def _vertical_text(text: str) -> str:
        return "\n".join(list(text)) if text else ""

    def _update_column_headers(self) -> None:
        for i, lbl in enumerate(self.col_header_labels):
            name = self.task_entries[i]["task_name"].get().strip() if i < len(self.task_entries) else ""
            lbl.configure(text=self._vertical_text(name or str(i + 1)))
        for i, lbl in enumerate(self.row_header_labels):
            name = self.task_entries[i]["task_name"].get().strip() if i < len(self.task_entries) else ""
            lbl.configure(text=name or str(i + 1))
        self._refresh_dsm_visualization()

    def _rebuild_tables(self) -> None:
        n = int(self.num_tasks_var.get())
        self.task_entries = []
        self.dsm_entries = []
        self.col_header_labels = []
        self.row_header_labels = []
        self.use_reordered_view = False
        self._clear_frame(self.tasks_frame)
        self._clear_frame(self.dsm_input_frame)
        self._clear_frame(self.dsm_visual_frame)

        headers = ["task_name", "base_cost", "base_duration", "cost_stddev", "duration_stddev"]
        for c, h in enumerate(headers):
            ttk.Label(self.tasks_frame, text=h).grid(row=0, column=c, padx=2, pady=2)

        for r in range(n):
            row_entries: dict[str, tk.Entry] = {}
            defaults = ["", "", "", "", ""]
            for c, key in enumerate(headers):
                e = ttk.Entry(self.tasks_frame, width=14)
                e.grid(row=r + 1, column=c, padx=2, pady=1)
                e.insert(0, defaults[c])
                if key == "task_name":
                    e.bind("<KeyRelease>", lambda _evt: self._update_column_headers())
                row_entries[key] = e
            self.task_entries.append(row_entries)

        canvas = tk.Canvas(self.dsm_input_frame, borderwidth=0)
        vscroll = ttk.Scrollbar(self.dsm_input_frame, orient="vertical", command=canvas.yview)
        hscroll = ttk.Scrollbar(self.dsm_input_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        vscroll.pack(side="right", fill="y")
        hscroll.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        grid = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=grid, anchor="nw")
        grid.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        ttk.Label(grid, text="DSM", width=10).grid(row=0, column=0, padx=1, pady=1)
        for c in range(n):
            lbl = ttk.Label(grid, text=self._vertical_text(str(c + 1)), width=4, anchor="center")
            lbl.grid(row=0, column=c + 1, padx=1, pady=1)
            self.col_header_labels.append(lbl)

        for r in range(n):
            row_name = ttk.Label(grid, text=str(r + 1), width=14, anchor="w")
            row_name.grid(row=r + 1, column=0, padx=1, pady=1, sticky="w")
            self.row_header_labels.append(row_name)
            row: List[tk.Widget] = []
            for c in range(n):
                if r == c:
                    cell = tk.Label(grid, text="╲", width=5, bg="#d9d9d9", anchor="center")
                    cell.grid(row=r + 1, column=c + 1, padx=1, pady=1)
                    row.append(cell)
                    continue
                e = ttk.Entry(grid, width=5)
                e.grid(row=r + 1, column=c + 1, padx=1, pady=1)
                e.bind("<KeyRelease>", lambda _evt: self._refresh_dsm_visualization())
                row.append(e)
            self.dsm_entries.append(row)

        ttk.Label(self.dsm_visual_frame, text="DSM可視化パネル", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", padx=6, pady=(4, 2))

        viz_tools = ttk.Frame(self.dsm_visual_frame)
        viz_tools.pack(fill="x")
        ttk.Button(viz_tools, text="DSM可視化を更新", command=self._refresh_dsm_visualization).pack(side="left", padx=4, pady=2)
        ttk.Button(viz_tools, text="DSM並べ替え", command=self._reorder_dsm_visualization).pack(side="left", padx=4, pady=2)

        viz_canvas_frame = ttk.Frame(self.dsm_visual_frame)
        viz_canvas_frame.pack(fill="both", expand=True)
        self.visual_canvas = tk.Canvas(viz_canvas_frame, borderwidth=0, bg="white", height=260)
        vsv = ttk.Scrollbar(viz_canvas_frame, orient="vertical", command=self.visual_canvas.yview)
        hsv = ttk.Scrollbar(viz_canvas_frame, orient="horizontal", command=self.visual_canvas.xview)
        self.visual_canvas.configure(yscrollcommand=vsv.set, xscrollcommand=hsv.set)
        vsv.pack(side="right", fill="y")
        hsv.pack(side="bottom", fill="x")
        self.visual_canvas.pack(side="left", fill="both", expand=True)

        self._update_column_headers()
        self._refresh_dsm_visualization()

    def _get_display_order(self, n: int) -> List[int]:
        if self.use_reordered_view and len(self.visual_order) == n:
            return self.visual_order
        return list(range(n))

    def _compute_upper_triangular_order(self, matrix: List[List[float]]) -> List[int]:
        n = len(matrix)
        stats = []
        for i in range(n):
            out_w = sum(matrix[i][j] for j in range(n) if i != j)
            in_w = sum(matrix[j][i] for j in range(n) if i != j)
            stats.append((i, out_w - in_w, out_w))
        stats.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return [i for i, _net, _out in stats]

    def _reorder_dsm_visualization(self) -> None:
        n = len(self.dsm_entries)
        if n == 0:
            return
        try:
            matrix = self._collect_dsm()
        except Exception:
            matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        self.visual_order = self._compute_upper_triangular_order(matrix)
        self.use_reordered_view = True
        self._refresh_dsm_visualization()

    @staticmethod
    def _dsm_cell_fill(src_r: int, src_c: int, value: float) -> str:
        if src_r == src_c:
            return "#e6e6e6"
        return "#2f80ed" if value > 0 else "#ffffff"

    def _refresh_dsm_visualization(self) -> None:
        if self.visual_canvas is None:
            return
        n = len(self.dsm_entries)
        if n == 0:
            self.visual_canvas.delete("all")
            return

        try:
            matrix = self._collect_dsm()
        except Exception:
            matrix = [[0.0 for _ in range(n)] for _ in range(n)]

        names = []
        for i in range(n):
            name = self.task_entries[i]["task_name"].get().strip() if i < len(self.task_entries) else ""
            names.append(name or str(i + 1))

        order = self._get_display_order(n)
        self.visual_order = order

        cell = 22
        left_w = 180
        top_h = 90
        w = left_w + cell * n + 20
        h = top_h + cell * n + 20

        c = self.visual_canvas
        c.delete("all")
        c.config(scrollregion=(0, 0, w, h))

        for vr, src_r in enumerate(order):
            for vc, src_c in enumerate(order):
                x1 = left_w + vc * cell
                y1 = top_h + vr * cell
                x2 = x1 + cell
                y2 = y1 + cell
                fill = self._dsm_cell_fill(src_r, src_c, matrix[src_r][src_c])
                c.create_rectangle(x1, y1, x2, y2, fill=fill, outline="#aaaaaa")

        for vr, src_r in enumerate(order):
            y = top_h + vr * cell + cell / 2
            label = names[src_r] if len(names[src_r]) <= 24 else names[src_r][:21] + "..."
            c.create_text(6, y, text=label, anchor="w", font=("TkDefaultFont", 9))

        for vc, src_c in enumerate(order):
            x = left_w + vc * cell + cell / 2
            label = names[src_c] if len(names[src_c]) <= 16 else names[src_c][:13] + "..."
            c.create_text(x, top_h - 6, text=label, angle=60, anchor="s", font=("TkDefaultFont", 8))

        c.create_text(left_w - 4, top_h - 4, text="DSM", anchor="se")

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
                if r == c:
                    row.append(0.0)
                    continue
                cell = self.dsm_entries[r][c]
                if not isinstance(cell, ttk.Entry):
                    row.append(0.0)
                    continue
                raw = cell.get().strip()
                v = 0.0 if raw == "" else float(raw)
                if not (0 <= v <= 1):
                    raise ValueError("DSMの値は0〜1で入力してください")
                row.append(v)
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
                    cell = self.dsm_entries[r][c]
                    if not isinstance(cell, ttk.Entry):
                        continue
                    cell.delete(0, tk.END)
                    if r != c:
                        cell.insert(0, str(dsm[r][c]))

            self._update_column_headers()
            self._refresh_dsm_visualization()

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
        ps1_path, bat_path = create_windows_start_files(args.project_dir)
        print(f"Windows起動ファイルを作成しました: {out}")
        print(f"ワンクリック起動(ps1): {ps1_path}")
        print(f"ワンクリック起動(bat): {bat_path}")
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
