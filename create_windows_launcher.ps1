$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath('Desktop')
$Launcher = Join-Path $Desktop 'DSM_Cost_Schedule_Simulator.bat'

$Bat = @"
@echo off
setlocal
REM DSM_LAUNCHER_VERSION=5
set "DIR=$ProjectDir"
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
"@

Set-Content -Path $Launcher -Value $Bat -Encoding Ascii
Write-Host "Created: $Launcher"
Write-Host "This launcher is fixed to: $ProjectDir"

$StartPs1 = Join-Path $ProjectDir 'start_latest_windows.ps1'
$StartBat = Join-Path $ProjectDir 'START_LATEST_DSM.bat'

$StartPs1Body = @"
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

if ((Test-Path (Join-Path $ProjectDir '.git')) -and (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Updating from Git..."
  try {
    git pull --ff-only | Out-Host
  } catch {
    Write-Host "Git update failed. Continue with local files."
  }
}

if (-not (Test-Path (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py'))) {
  Write-Host "dsm_cost_schedule_sim.py が見つかりません: $ProjectDir"
  pause
  exit 1
}

Write-Host "Launching latest GUI from: $ProjectDir"

$ok = $false
try {
  & py -3 (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py') --gui
  if ($LASTEXITCODE -eq 0) { $ok = $true }
} catch {}

if (-not $ok) {
  & python (Join-Path $ProjectDir 'dsm_cost_schedule_sim.py') --gui
  if ($LASTEXITCODE -eq 0) { $ok = $true }
}

if (-not $ok) {
  Write-Host "Launch failed. Run in PowerShell: python dsm_cost_schedule_sim.py --gui"
  pause
  exit 1
}
"@

$StartBatBody = @"
@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_latest_windows.ps1"
if errorlevel 1 (
  echo.
  echo Failed to refresh/start launcher.
  pause
)
endlocal
"@

Set-Content -Path $StartPs1 -Value $StartPs1Body -Encoding UTF8
Set-Content -Path $StartBat -Value $StartBatBody -Encoding Ascii
Write-Host "Created: $StartPs1"
Write-Host "Created: $StartBat"
