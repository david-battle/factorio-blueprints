#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TESTS_DIR="$PROJECT_DIR/tests"
RUNTIME_DIR="$PROJECT_DIR/runtime"
ACTION_FILE="$SCRIPT_DIR/jimbo-action.json"
PID_FILE="$RUNTIME_DIR/jimbo.pid"
STDOUT_LOG="$RUNTIME_DIR/listener.stdout.log"
STDERR_LOG="$RUNTIME_DIR/listener.stderr.log"

VENV_PYTHON="/mnt/d/jimbo-venv/bin/python3"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
fi

if [[ ! -f "$ACTION_FILE" ]]; then
    echo "Jimbo action file not found: $ACTION_FILE" >&2
    exit 1
fi

ACTION=$("$PYTHON" -c "import json,sys; print(json.load(open(sys.argv[1]))['action'])" "$ACTION_FILE")
ARGUMENTS=$("$PYTHON" -c "
import json, sys
args = json.load(open(sys.argv[1])).get('arguments', [])
print(' '.join(str(a) for a in args))
" "$ACTION_FILE")

case "$ACTION" in
    test|bot|start|stop|restart|status) ;;
    *)
        echo "Unsupported Jimbo project action '$ACTION'" >&2
        exit 1
        ;;
esac

get_pid() {
    if [[ ! -f "$PID_FILE" ]]; then
        return 1
    fi
    local saved_pid
    saved_pid=$(<"$PID_FILE")
    if kill -0 "$saved_pid" 2>/dev/null; then
        echo "$saved_pid"
        return 0
    fi
    rm -f "$PID_FILE"
    return 1
}

stop_listener() {
    local pid
    if ! pid=$(get_pid); then
        echo "Jimbo listener is not running."
        return
    fi
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 50); do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 0.1
    done
    rm -f "$PID_FILE"
    echo "Stopped Jimbo listener PID $pid."
}

start_listener() {
    local pid
    if pid=$(get_pid); then
        echo "Jimbo listener is already running as PID $pid."
        return
    fi
    mkdir -p "$RUNTIME_DIR"
    # Pass the selected bot mode exactly once from the approved action file.
    nohup "$PYTHON" -u "$PROJECT_DIR/jimbo_bot.py" $ARGUMENTS \
        >"$STDOUT_LOG" 2>"$STDERR_LOG" &
    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"
    echo "Started Jimbo listener PID $new_pid."
}

cd "$PROJECT_DIR"
case "$ACTION" in
    test)
        "$PYTHON" -m unittest discover -s "$TESTS_DIR" -v
        ;;
    bot)
        "$PYTHON" -u "$PROJECT_DIR/jimbo_bot.py" $ARGUMENTS
        ;;
    start)  start_listener ;;
    stop)   stop_listener ;;
    restart)
        stop_listener
        start_listener
        ;;
    status)
        if pid=$(get_pid); then
            echo "Jimbo listener is running as PID $pid."
        else
            echo "Jimbo listener is not running."
        fi
        ;;
esac
