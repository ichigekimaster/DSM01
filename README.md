# DSM コスト・期間リスクシミュレーション（Win11対応）

Browning and Eppinger の
**"Modeling Impacts of Process Architecture on Cost and Schedule Risk in Product Development"**
を再現するための、DSMベースのコスト・期間シミュレーションソフトです。

## 特徴
- **GUIで数値入力してシミュレーション実行**
- `simulation_results.csv` と `cost_duration_scatter.svg` を出力
- CLIでも実行可能
- 依存ライブラリ不要（標準ライブラリのみ）

## Win11での使い方（最優先）

### 0. いちばん簡単（これだけ）
`START_LATEST_DSM.bat` をダブルクリックしてください。
- そのフォルダの dsm_cost_schedule_sim.py を直接起動（最短）
- Git管理(clone)している場合は、起動時に `git pull --ff-only` で自動更新を試みます

`START_LATEST_DSM.bat` が見当たらない場合は、次の1行で自動作成してください。
```powershell
python dsm_cost_schedule_sim.py --create-win-launcher
```

PowerShellで実行する場合は次の1行です。
```powershell
powershell -ExecutionPolicy Bypass -File .\start_latest_windows.ps1
```

※ 自動更新が効くのは Git clone したフォルダです（ZIP展開フォルダは対象外）。

### 0.5 system32 にいても作成できる方法（コピペ1回）
PowerShellで次をそのまま実行してください（`cd` 不要）。
```powershell
$roots=@("$env:USERPROFILE\Desktop","$env:USERPROFILE\Downloads","$env:USERPROFILE\Documents"); $ps1=Get-ChildItem -Path $roots -Filter create_windows_launcher.ps1 -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName; if($ps1){ powershell -NoProfile -ExecutionPolicy Bypass -File $ps1 } else { Write-Host "create_windows_launcher.ps1 が見つかりません" }
```
同じ処理をファイルで実行したい場合は `create_win_launcher_anywhere.ps1` を使ってください。

### 0.8 GitHub画面で最新版をPCへ反映する手順（画像の画面向け）
※ 右側の「昨日」は更新表示なので、操作は不要です。

1) GitHubで緑の「コード」ボタンを押して `Download ZIP`
2) ZIPを展開
3) 展開した中身で、PCの `C:\Users\hp\Desktop\DSM01-main\DSM01-main` を上書き
4) 上書き後に PowerShell で次を実行
```powershell
cd C:\Users\hp\Desktop\DSM01-main\DSM01-main
powershell -ExecutionPolicy Bypass -File .\create_windows_launcher.ps1
```
5) 次の2ファイルが存在するか確認
```powershell
Test-Path .\START_LATEST_DSM.bat
Test-Path .\start_latest_windows.ps1
```
6) `START_LATEST_DSM.bat` をダブルクリック

### 1. GUIを直接起動
PowerShell でプロジェクトフォルダへ移動して実行:

```powershell
python dsm_cost_schedule_sim.py
```

引数なしでGUIが起動します。タスク情報・DSM・試行設定を入力して実行できます。

DSM画面の仕様（Yassine 論文の表現に合わせた表示）:
- 起動時のDSMサイズは **20×20**
- `＋` / `－` ボタンで行列サイズを増減
- 対角セルは自己遷移を表さないため斜線で無効化
- 行の `task_name` を入力すると、列ヘッダに同期表示（縦書き表示）

### 2. デスクトップに「クリック起動ファイル」を作成
#### 方法A（推奨・PowerShell）
```powershell
python dsm_cost_schedule_sim.py --create-win-launcher
```

作成先既定: `~/Desktop/DSM_Cost_Schedule_Simulator.bat`

#### 方法B（PowerShellスクリプト）
```powershell
powershell -ExecutionPolicy Bypass -File .\create_windows_launcher.ps1
```

### 2.5 うまくいかない時（超かんたん）
1) まず古いランチャーを削除
```powershell
Remove-Item "$env:USERPROFILE\Desktop\DSM_Cost_Schedule_Simulator.bat" -ErrorAction SilentlyContinue
```
2) プロジェクトフォルダで再生成
```powershell
cd C:\Users\hp\Desktop\DSM01\DSM01-main\DSM01-main
powershell -ExecutionPolicy Bypass -File .\create_windows_launcher.ps1
```
3) 内容確認（`DSM_LAUNCHER_VERSION=5` と `py -3 dsm_cost_schedule_sim.py --gui` があればOK）
```powershell
Get-Content "$env:USERPROFILE\Desktop\DSM_Cost_Schedule_Simulator.bat"
```

### 3. クリック起動
デスクトップの `DSM_Cost_Schedule_Simulator.bat` をダブルクリックするとGUIが起動します。

※ Windowsランチャーは Desktop / Downloads / Documents 配下から
ランチャー生成時に実行したフォルダへ固定して起動します（別フォルダの古い版は開きません）。

※ GUIタイトルに `DSM-20x20` と表示されていれば最新レイアウト版です。

---

## CLI実行（必要な場合）
### 空テンプレート作成
```bash
python dsm_cost_schedule_sim.py --create-templates --template-dir templates --template-tasks 10
```

### シミュレーション実行
```bash
python dsm_cost_schedule_sim.py \
  --tasks templates/tasks_template.csv \
  --dsm templates/dsm_template.csv \
  --config templates/config_template.json \
  --out-csv simulation_results.csv \
  --out-svg cost_duration_scatter.svg
```

## テスト
```bash
python -m pytest -q
```
