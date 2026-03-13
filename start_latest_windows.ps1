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
