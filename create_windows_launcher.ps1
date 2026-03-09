$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath('Desktop')
$Launcher = Join-Path $Desktop 'DSM_Cost_Schedule_Simulator.bat'

$Bat = @"
@echo off
setlocal
cd /d "$ProjectDir"
python dsm_cost_schedule_sim.py --gui
if errorlevel 1 (
  echo.
  echo 起動に失敗しました。PythonのインストールとPATH設定を確認してください。
  pause
)
endlocal
"@

Set-Content -Path $Launcher -Value $Bat -Encoding UTF8
Write-Host "作成完了: $Launcher"

