#!/usr/bin/env bash
# Serve ./app and open it full-screen in Chromium. Exits once the page has loaded.
set -euo pipefail
(setsid nohup python3 _shared/state_server.py >/tmp/deepgym_server.log 2>&1 &)
(setsid nohup chromium --no-first-run --no-default-browser-check --disable-gpu \
  --disable-features=Translate --password-store=basic --kiosk \
  --remote-debugging-port=9222 --user-data-dir=/tmp/deepgym_chrome \
  http://127.0.0.1:8000/ >/tmp/deepgym_chrome.log 2>&1 &)
for _ in $(seq 60); do
  if curl -sf http://127.0.0.1:9222/json | grep -q '"title": "DeepGym'; then
    sleep 1
    exit 0
  fi
  sleep 0.5
done
echo 'app did not load' >&2
exit 1
