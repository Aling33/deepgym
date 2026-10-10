#!/usr/bin/env bash
# Keep the agent in the GUI: no terminals, run dialogs, file manager, or browser devtools.
# Usage: bash _shared/lockdown.sh [app-to-keep ...]   e.g. `lockdown.sh thunar`
set -euo pipefail
sudo -n true

sudo mkdir -p /etc/chromium/policies/managed
echo '{"DeveloperToolsAvailability": 2,
       "URLBlocklist": ["javascript://*", "chrome://*", "devtools://*", "file://*", "view-source:*"]}' \
  | sudo tee /etc/chromium/policies/managed/deepgym.json >/dev/null

# Thunar's custom actions include "Open Terminal Here".
sudo rm -f /etc/xdg/Thunar/uca.xml

# The panel and desktop menus can add launchers or shortcuts that run any command.
for bin in xfce4-terminal x-terminal-emulator xterm xfce4-appfinder exo-open thunar \
           xfce4-panel xfdesktop xfce4-settings-manager xfce4-settings-editor \
           xfce4-keyboard-settings; do
  case " $* " in *" $bin "*) continue ;; esac
  path=$(command -v "$bin" || true)
  if [ -n "$path" ]; then
    sudo chmod 000 "$(readlink -f "$path")"
  fi
done
pkill -x xfce4-panel || true
pkill -x xfdesktop || true
