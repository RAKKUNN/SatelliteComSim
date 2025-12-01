#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import signal
import argparse
import subprocess
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 관리할 프로세스 정의 (시작 순서대로)
PROCS = [
    # (name, script_path_rel)
    ("test4", "test4.py"),
    ("test3", "test3.py"),
    ("test2", "test2.py"),
    ("test1", "test1.py"),
]

def pid_file(name: str) -> Path:
    return LOG_DIR / f"{name}.pid"

def log_file(name: str) -> Path:
    return LOG_DIR / f"{name}.log"

def abs_script(name: str, rel: str) -> Path:
    return (ROOT / rel).resolve()

def _read_pid(p: Path) -> Optional[int]:
    try:
        s = p.read_text().strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None

def _proc_cmdline(pid: int) -> str:
    """리눅스 /proc/<pid>/cmdline 조회 (스페이스 대신 NUL 구분)"""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            data = f.read().replace(b"\x00", b" ").strip()
            return data.decode(errors="ignore")
    except Exception:
        return ""

def _proc_exists(pid: int) -> bool:
    """pid가 살아있는지(또는 권한상 확인 가능한지) 확인"""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 살아있지만 권한이 없을 수 있음
        return True
    except Exception:
        return False

def _matches_script(pid: int, script_path: Path) -> bool:
    """해당 pid가 우리가 원하는 스크립트를 실행 중인지 확인"""
    cmd = _proc_cmdline(pid)
    target = str(script_path)
    return (target in cmd)

def is_running(name: str, script_path: Path) -> Tuple[bool, Optional[int]]:
    """
    반환: (실행중여부, pid)
    - pid파일이 있고, 그 PID가 살아있고, 해당 스크립트를 실행 중이면 True
    - 아니면 False (이 때, stale pidfile은 호출측에서 정리)
    """
    pf = pid_file(name)
    pid = _read_pid(pf)
    if not pid:
        return (False, None)
    if not _proc_exists(pid):
        return (False, None)
    if not _matches_script(pid, script_path):
        # 같은 PID가 다른 프로그램에 재사용된 경우
        return (False, None)
    return (True, pid)

def _popen_detached(cmd, cwd: str, log_fd):
    """플랫폼별 백그라운드(detached group) 실행"""
    if os.name == "nt":
        # Windows: 새 프로세스 그룹
        return subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        # POSIX: 새 프로세스 그룹
        return subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            preexec_fn=os.setsid
        )

def start_one(name: str, script_rel: str, skip_if_running: bool = True) -> bool:
    spath = abs_script(name, script_rel)
    if not spath.is_file():
        print(f"[ERROR] {name}: 스크립트를 찾을 수 없음 -> {spath}")
        return False

    running, pid = is_running(name, spath)
    if running:
        if skip_if_running:
            print(f"[SKIP] {name}: 이미 실행 중 (pid={pid})")
            return True
        else:
            stop_one(name, script_rel)
            time.sleep(0.3)

    # 혹시 남아 있던 오래된 pid 파일은 여기서 정리
    pf = pid_file(name)
    if pf.exists():
        old = _read_pid(pf)
        if (not old) or (not _proc_exists(old)) or (not _matches_script(old, spath)):
            try:
                pf.unlink()
            except Exception:
                pass

    lf = log_file(name)
    lf.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(lf, "a", buffering=1, encoding="utf-8", errors="ignore")

    cmd = [sys.executable, "-u", str(spath)]
    try:
        p = _popen_detached(cmd, str(ROOT), log_fd)
        pid_file(name).write_text(str(p.pid))
        print(f"[OK  ] {name}: 시작됨 (pid={p.pid}) -> {lf}")
        return True
    except Exception as e:
        print(f"[ERROR] {name}: 시작 실패 -> {e}")
        return False

def stop_one(name: str, script_rel: str) -> bool:
    spath = abs_script(name, script_rel)
    running, pid = is_running(name, spath)
    pf = pid_file(name)
    if not running:
        if pf.exists():
            try:
                pf.unlink()
            except Exception:
                pass
        print(f"[OK  ] {name}: 이미 중지됨")
        return True

    # 프로세스 그룹 종료 (SIGTERM → 대기 → SIGKILL)
    try:
        if os.name == "nt":
            # Windows: 개별 PID에 Ctrl-C 못보냄. 일반 TERM 유사 동작 없음.
            # 가능한 강제 종료 시그널 대체로 terminate 시도 후 kill 대체.
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        else:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass

    for _ in range(20):
        time.sleep(0.1)
        if not _proc_exists(pid):
            break
    else:
        try:
            if os.name == "nt":
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
            else:
                os.killpg(pid, signal.SIGKILL)
        except Exception:
            pass

    if pf.exists():
        try:
            pf.unlink()
        except Exception:
            pass

    print(f"[OK  ] {name}: 중지됨")
    return True

def status_one(name: str, script_rel: str):
    spath = abs_script(name, script_rel)
    running, pid = is_running(name, spath)
    if running:
        print(f"[RUN ] {name}: pid={pid} log={log_file(name)}")
    else:
        print(f"[STOP] {name}")

def action_start(force: bool = False):
    print(f"[INFO] start: test4 -> test3 -> test2 -> test1 (background)")
    print(f"[INFO] ROOT={ROOT}")
    print(f"[INFO] LOG_DIR={LOG_DIR}")
    if force:
        action_stop()
        time.sleep(0.5)
    for name, rel in PROCS:
        ok = start_one(name, rel, skip_if_running=not force)
        time.sleep(0.2 if ok else 0.0)
    print("[DONE] start 완료. 로그: newGS/log/test*.log")

def action_stop():
    print("[INFO] stop: test1 -> test2 -> test3 -> test4")
    for name, rel in reversed(PROCS):
        stop_one(name, rel)
        time.sleep(0.1)
    print("[DONE] stop 완료.")

def action_restart():
    print("[INFO] restart")
    action_stop()
    time.sleep(0.5)
    action_start(force=False)

def action_status():
    print("[INFO] status:")
    for name, rel in PROCS:
        status_one(name, rel)

def parse_args():
    p = argparse.ArgumentParser(description="Batch launcher for test4->test3->test2->test1")
    p.add_argument("action", nargs="?", default="start",
                   choices=["start", "stop", "restart", "status"])
    p.add_argument("--force", action="store_true", help="start 전에 stop 수행 (강제 재시작)")
    return p.parse_args()

def main():
    args = parse_args()
    if args.action == "start":
        action_start(force=args.force)
    elif args.action == "stop":
        action_stop()
    elif args.action == "restart":
        action_restart()
    elif args.action == "status":
        action_status()

if __name__ == "__main__":
    main()

