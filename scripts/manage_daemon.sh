#!/usr/bin/env bash
PID_FILE="/tmp/spark-otp.pid"
LOG_FILE="/tmp/spark-otp.log"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$(which python3)"
PLIST_NAME="com.spark_otp.daemon.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"
SRC_PLIST="$PROJECT_DIR/scripts/$PLIST_NAME"

case "$1" in
  start)
    HEALTH=$(curl -s http://127.0.0.1:9428/api/health 2>/dev/null)
    if [ -n "$HEALTH" ]; then
      echo "spark-otp daemon is already running: $HEALTH"
      exit 0
    fi
    echo "Starting spark-otp daemon on port 9428..."
    nohup "$PYTHON_BIN" "$PROJECT_DIR/cli.py" serve --port 9428 > "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    sleep 1
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
