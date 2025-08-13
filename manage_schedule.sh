#!/bin/bash

# FDA 510k Watcher 스케줄 관리 스크립트

case "$1" in
    "start")
        echo "🚀 FDA 510k Watcher 스케줄 시작..."
        launchctl load ~/Library/LaunchAgents/com.fda510kwatcher.plist
        echo "✅ 스케줄이 시작되었습니다. 매일 아침 7시에 실행됩니다."
        ;;
    "stop")
        echo "⏹️  FDA 510k Watcher 스케줄 중지..."
        launchctl unload ~/Library/LaunchAgents/com.fda510kwatcher.plist
        echo "✅ 스케줄이 중지되었습니다."
        ;;
    "status")
        echo "📊 FDA 510k Watcher 스케줄 상태 확인..."
        launchctl list | grep fda510kwatcher
        echo ""
        echo "📁 로그 파일 상태:"
        ls -la fda_510k_watcher*.log 2>/dev/null || echo "로그 파일이 없습니다"
        echo ""
        echo "📁 상태 파일:"
        ls -la fda_510k_html_state.json 2>/dev/null || echo "상태 파일이 없습니다"
        ;;
    "restart")
        echo "🔄 FDA 510k Watcher 스케줄 재시작..."
        launchctl unload ~/Library/LaunchAgents/com.fda510kwatcher.plist 2>/dev/null
        sleep 2
        launchctl load ~/Library/LaunchAgents/com.fda510kwatcher.plist
        echo "✅ 스케줄이 재시작되었습니다."
        ;;
    "test")
        echo "🧪 FDA 510k Watcher 테스트 실행..."
        python test_schedule.py
        ;;
    "logs")
        echo "📋 FDA 510k Watcher 로그 확인..."
        echo "=== 일반 로그 ==="
        tail -20 fda_510k_watcher.log 2>/dev/null || echo "로그 파일이 없습니다"
        echo ""
        echo "=== 에러 로그 ==="
        tail -20 fda_510k_watcher_error.log 2>/dev/null || echo "에러 로그 파일이 없습니다"
        ;;
    *)
        echo "FDA 510k Watcher 스케줄 관리 스크립트"
        echo ""
        echo "사용법: $0 {start|stop|status|restart|test|logs}"
        echo ""
        echo "명령어:"
        echo "  start   - 스케줄 시작"
        echo "  stop    - 스케줄 중지"
        echo "  status  - 스케줄 상태 확인"
        echo "  restart - 스케줄 재시작"
        echo "  test    - 스케줄 테스트"
        echo "  logs    - 로그 파일 확인"
        echo ""
        echo "현재 설정: 매일 아침 7시 자동 실행"
        ;;
esac
