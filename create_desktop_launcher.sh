#!/usr/bin/env bash
set -euo pipefail

APP_NAME="DSM_Cost_Schedule_Simulator.desktop"
TARGET_SCRIPT="/workspace/DSM01/dsm_cost_schedule_sim.py"

create_launcher() {
  local desktop_dir="$1"
  mkdir -p "$desktop_dir"
  cat > "$desktop_dir/$APP_NAME" <<DESK
[Desktop Entry]
Type=Application
Version=1.0
Name=DSM Cost Schedule Simulator
Comment=DSM-based cost and schedule Monte Carlo simulator
Exec=python3 $TARGET_SCRIPT --gui
Path=/workspace/DSM01
Terminal=false
Categories=Science;Education;
DESK
  chmod +x "$desktop_dir/$APP_NAME"
  echo "Created: $desktop_dir/$APP_NAME"
}

# Current user's desktop
if [[ -n "${HOME:-}" ]]; then
  create_launcher "$HOME/Desktop"
fi

# Common Linux user desktops
for dir in /home/*/Desktop; do
  if [[ -d "$dir" ]]; then
    create_launcher "$dir"
  fi
done
