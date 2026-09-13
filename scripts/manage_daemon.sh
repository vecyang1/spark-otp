#!/usr/bin/env bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PID_FILE="/tmp/spark-otp.pid"
LOG_FILE="/tmp/spark-otp.log"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$(which python3)"
PLIST_NAME="com.spark_otp.daemon.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"
SRC_PLIST="$PROJECT_DIR/scripts/$PLIST_NAME"
LEGACY_PLISTS=(
  "$HOME/Library/LaunchAgents/com.worldinspirelab.spark-otp.plist"
  "$HOME/Library/LaunchAgents/com.spark-otp.daemon.plist"
)

cleanup_legacy_plists() {
  for lp in "${LEGACY_PLISTS[@]}"; do
    if [ -f "$lp" ] && [ "$lp" != "$TARGET_PLIST" ]; then
      launchctl unload "$lp" 2>/dev/null || true
      rm -f "$lp"
    fi
  done
}

case "$1" in
  start)
    HEALTH=$(curl -s http://127.0.0.1:9428/api/health 2>/dev/null)
    if [ -n "$HEALTH" ]; then
      echo "spark-otp daemon is already running: $HEALTH"
      exit 0
    fi
    if [ -f "$TARGET_PLIST" ]; then
      echo "Starting spark-otp daemon via LaunchAgent..."
      cleanup_legacy_plists
      launchctl unload "$TARGET_PLIST" 2>/dev/null || true
      launchctl load "$TARGET_PLIST"
      for i in {1..20}; do
        HEALTH=$(curl -s http://127.0.0.1:9428/api/health 2>/dev/null)
        if [ -n "$HEALTH" ]; then break; fi
        sleep 0.5
      done
      if [ -n "$HEALTH" ]; then
        echo "spark-otp daemon started successfully via LaunchAgent"
      else
        echo "Failed to start daemon via LaunchAgent. Check $LOG_FILE and /tmp/spark-otp-err.log"
        exit 1
      fi
      exit 0
    fi
    echo "Starting spark-otp daemon on port 9428..."
    nohup "$PYTHON_BIN" "$PROJECT_DIR/cli.py" serve --port 9428 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    for i in {1..20}; do
      if kill -0 $PID 2>/dev/null; then
        HEALTH=$(curl -s http://127.0.0.1:9428/api/health 2>/dev/null)
        if [ -n "$HEALTH" ]; then break; fi
      fi
      sleep 0.5
    done
    if kill -0 $PID 2>/dev/null; then
      echo "spark-otp daemon started successfully (PID $PID)"
    else
      echo "Failed to start daemon. Check $LOG_FILE"
      exit 1
    fi
    ;;
  run)
    # Foreground runner for launchd / process supervisor
    exec "$PYTHON_BIN" "$PROJECT_DIR/cli.py" serve --port 9428
    ;;
  stop)
    echo "Stopping spark-otp daemon..."
    cleanup_legacy_plists
    if [ -f "$TARGET_PLIST" ]; then
      launchctl unload "$TARGET_PLIST" 2>/dev/null || true
    fi
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      kill "$PID" 2>/dev/null || true
      rm -f "$PID_FILE"
    fi
    pkill -f "cli\.py.*serve.*9428" 2>/dev/null || true
    echo "Stopped"
    ;;
  status)
    HEALTH=$(curl -s http://127.0.0.1:9428/api/health 2>/dev/null)
    PID=$(lsof -ti :9428 2>/dev/null | head -n 1)
    if [ -n "$HEALTH" ]; then
      echo "spark-otp daemon is RUNNING (PID $PID, Port 9428)"
      echo "Health: $HEALTH"
    else
      echo "spark-otp daemon is STOPPED"
    fi
    ;;
  restart)
    $0 stop
    sleep 1
    $0 start
    ;;
  enable-autostart)
    echo "Enabling macOS auto-start on login (LaunchAgent)..."
    cleanup_legacy_plists
    # Kill any manual process holding port 9428 first
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      kill "$PID" 2>/dev/null || true
      rm -f "$PID_FILE"
    fi
    pkill -f "cli\.py.*serve.*9428" 2>/dev/null || true
    sleep 1
    mkdir -p "$HOME/Library/LaunchAgents"
    sed "s|__SPARK_OTP_SCRIPT__|$PROJECT_DIR/scripts/manage_daemon.sh|g" "$SRC_PLIST" > "$TARGET_PLIST"
    launchctl unload "$TARGET_PLIST" 2>/dev/null || true
    launchctl load "$TARGET_PLIST"
    sleep 1
    echo "Auto-start enabled! Daemon will automatically start whenever your Mac boots or logs in."
    ;;
  disable-autostart)
    echo "Disabling macOS auto-start..."
    cleanup_legacy_plists
    launchctl unload "$TARGET_PLIST" 2>/dev/null || true
    rm -f "$TARGET_PLIST"
    echo "Auto-start disabled."
    ;;
  logs)
    if [ -f "$LOG_FILE" ]; then
      tail -n 50 "$LOG_FILE"
    else
      echo "No log file found at $LOG_FILE"
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs|enable-autostart|disable-autostart|run}"
    exit 1
    ;;
esac
