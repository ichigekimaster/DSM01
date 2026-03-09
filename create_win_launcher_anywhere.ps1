$ErrorActionPreference = "Stop"

$roots = @(
  (Join-Path $env:USERPROFILE 'Desktop'),
  (Join-Path $env:USERPROFILE 'Downloads'),
  (Join-Path $env:USERPROFILE 'Documents')
)

$launcherPs1 = Get-ChildItem -Path $roots -Filter create_windows_launcher.ps1 -Recurse -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 -ExpandProperty FullName

if (-not $launcherPs1) {
  Write-Host "create_windows_launcher.ps1 が見つかりませんでした。"
  Write-Host "Desktop / Downloads / Documents に展開したフォルダがあるか確認してください。"
  exit 1
}

Write-Host "Found: $launcherPs1"
Write-Host "起動ファイルを再生成します..."
powershell -NoProfile -ExecutionPolicy Bypass -File $launcherPs1

$desktopBat = Join-Path ([Environment]::GetFolderPath('Desktop')) 'DSM_Cost_Schedule_Simulator.bat'
if (Test-Path $desktopBat) {
  Write-Host "完了: $desktopBat"
} else {
  Write-Host "失敗: $desktopBat が作成されませんでした。"
  exit 1
}
