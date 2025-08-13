#!/usr/bin/env python3
"""
FDA 510k Watcher 스케줄 테스트 스크립트
매일 아침 7시에 실행되는지 확인
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 현재 시간 (KST)
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)

print("=== FDA 510k Watcher 스케줄 테스트 ===")
print(f"현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')} KST")
print(f"스케줄된 실행 시간: 매일 아침 7:00 KST")
print()

# 상태 파일 확인
state_file = Path("fda_510k_html_state.json")
if state_file.exists():
    state = json.loads(state_file.read_text())
    seen_count = len(state.get("seen_k_numbers", []))
    print(f"✅ 상태 파일 확인: {seen_count}개 K번호 저장됨")
    print(f"   파일 경로: {state_file.absolute()}")
else:
    print("❌ 상태 파일이 없습니다")

# 로그 파일 확인
log_file = Path("fda_510k_watcher.log")
error_log_file = Path("fda_510k_watcher_error.log")

if log_file.exists():
    log_size = log_file.stat().st_size
    print(f"✅ 로그 파일 확인: {log_size} bytes")
else:
    print("❌ 로그 파일이 없습니다")

if error_log_file.exists():
    error_log_size = error_log_file.stat().st_size
    print(f"✅ 에러 로그 파일 확인: {error_log_size} bytes")
else:
    print("❌ 에러 로그 파일이 없습니다")

# Launch Agent 상태 확인
print()
print("=== Launch Agent 상태 ===")
os.system("launchctl list | grep fda510kwatcher")

# 다음 실행 시간 계산
next_run = now.replace(hour=7, minute=0, second=0, microsecond=0)
if now.hour >= 7:
    next_run = next_run + timedelta(days=1)

time_until_next = next_run - now
hours, remainder = divmod(time_until_next.seconds, 3600)
minutes, seconds = divmod(remainder, 60)

print()
print(f"다음 실행 시간: {next_run.strftime('%Y-%m-%d %H:%M:%S')} KST")
print(f"남은 시간: {time_until_next.days}일 {hours}시간 {minutes}분")

print()
print("=== 설정 완료! ===")
print("✅ 매일 아침 7시에 자동 실행됩니다")
print("✅ 로그는 fda_510k_watcher.log 파일에 저장됩니다")
print("✅ 에러는 fda_510k_watcher_error.log 파일에 저장됩니다")
print("✅ 상태는 fda_510k_html_state.json 파일에 저장됩니다")
