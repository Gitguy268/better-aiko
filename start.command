#!/bin/sh
# Double-click to browse the icons: serves this folder and opens the page.
cd "$(dirname "$0")" || exit 1
PORT=8794
( sleep 1; open "http://localhost:$PORT/" ) &
exec python3 -m http.server "$PORT" --bind 127.0.0.1
