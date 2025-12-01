#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, time, socket, pathlib, subprocess, shlex, signal, traceback, threading

# ===== 설정 =====
GS_LISTEN_HOST = os.getenv("GS_LISTEN_HOST", "0.0.0.0")
GS_LISTEN_PORT = int(os.getenv("GS_LISTEN_PORT", "50000"))   # GS→test1 수신
UPLINK_DST_HOST = os.getenv("UPLINK_DST_HOST", "127.0.0.1")
UPLINK_DST_PORT = int(os.getenv("UPLINK_DST_PORT", "8600"))  # GNURadio 미사용 → CI_LAB 직결

LOG_DIR = pathlib.Path(os.getenv("LOG_DIR", "log")); LOG_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH = LOG_DIR / "sample_app_sent.csv"

SETUP_SCRIPT = os.getenv("TOLAB_SETUP_SCRIPT",
    str((pathlib.Path(__file__).parent / "scripts" / "setup_tolab_08a9.sh").resolve()))
SETUP_TIMEOUT_SEC = int(os.getenv("TOLAB_SETUP_TIMEOUT_SEC", "12"))
SKIP_SETUP = os.getenv("TOLAB_SKIP_SETUP", "0") == "1"

# SAMPLE_APP SEND_TEXT 명령
SAMPLE_APP_CMD_MID = 0x1882
SEND_TEXT_CC = 3

# ===== 유틸 =====
def now_ts():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def ensure_csv_header(path: pathlib.Path):
    found = path.exists() and path.stat().st_size > 0
    f = path.open("a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if not found:
        w.writerow([
            "ts","direction","id","text","mid_hex","apid_hex","cc_dec","len",
            "src_ip","src_port","head_hex16","text_hex","bits"
        ])
    return f, w

def to_hex(b: bytes) -> str:
    return "".join(f"{x:02X}" for x in b)

def bytes_to_bits(b: bytes) -> str:
    return "".join(f"{x:08b}" for x in b)

def parse_mid_apid_cc(data: bytes):
    """
    MID(16b Big-endian), APID(하위 11b), CC(cmd code=byte6) 추출
    """
    mid = apid = cc = None
    if len(data) >= 2:
        mid = (data[0] << 8) | data[1]   # ✅ MID=StreamID 전체 16비트
        apid = mid & 0x07FF              # ✅ APID=하위 11비트
    if len(data) > 6:
        cc = data[6]
    return mid, apid, cc

def parse_id_text_if_send_text(data: bytes):
    """
    SEND_TEXT(0x1882, cc=3)일 때만 'ID:TEXT\\x00...' 파싱
    텍스트 시작 오프셋은 명령 구조에 맞게 8바이트 이후로 가정.
    """
    mid, _, cc = parse_mid_apid_cc(data)
    if mid != SAMPLE_APP_CMD_MID or cc != SEND_TEXT_CC:
        return None, ""
    if len(data) <= 8:
        return None, ""
    payload = data[8:]
    payload = payload.split(b'\x00', 1)[0]
    try:
        s = payload.decode('utf-8', errors='ignore')
    except Exception:
        return None, ""
    parts = s.split(':', 1)
    if len(parts) == 2 and parts[0].isdigit():
        return int(parts[0]), parts[1]
    return None, s

# ===== 스크립트 비동기 실행 =====
def run_setup_script_async():
    if SKIP_SETUP:
        print(f"[{now_ts()}] [INIT] skip by env TOLAB_SKIP_SETUP=1")
        return
    if not os.path.isfile(SETUP_SCRIPT):
        print(f"[{now_ts()}] [INIT][WARN] setup script not found: {SETUP_SCRIPT}")
        return
    def _run():
        cmd = ["/usr/bin/env", "bash", SETUP_SCRIPT]
        print(f"[{now_ts()}] [INIT] running (async): {' '.join(shlex.quote(c) for c in cmd)}")
        try:
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=SETUP_TIMEOUT_SEC, check=False, text=True)
            print(f"[{now_ts()}] [INIT] rc={cp.returncode}")
            if cp.stdout: print(f"[INIT][STDOUT]\n{cp.stdout.strip()}")
            if cp.stderr: print(f"[INIT][STDERR]\n{cp.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"[{now_ts()}] [INIT][ERROR] setup timeout ({SETUP_TIMEOUT_SEC}s)")
        except Exception as e:
            print(f"[{now_ts()}] [INIT][EXCEPTION] {e}\n{traceback.format_exc()}")
    threading.Thread(target=_run, daemon=True).start()

def main():
    print(f"[{now_ts()}] test1 starting…")
    print(f"[{now_ts()}] __file__={__file__}")
    print(f"[{now_ts()}] CSV_PATH={CSV_PATH.resolve()}")

    # 1) 수신 바인딩
    try:
        in_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        in_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        in_sock.bind((GS_LISTEN_HOST, GS_LISTEN_PORT))
        print(f"[{now_ts()}] listening on {GS_LISTEN_HOST}:{GS_LISTEN_PORT}")
    except Exception as e:
        print(f"[{now_ts()}] [BIND][ERROR] {e}\n{traceback.format_exc()}"); sys.exit(1)

    out_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[{now_ts()}] forwarding to {UPLINK_DST_HOST}:{UPLINK_DST_PORT}")

    f, writer = ensure_csv_header(CSV_PATH)
    last_flush = time.time()

    # 2) 시작 직후 TO_LAB 초기화 스크립트
    run_setup_script_async()

    running = True
    def _handle(sig, frame):
        nonlocal running; running = False
    signal.signal(signal.SIGINT, _handle); signal.signal(signal.SIGTERM, _handle)

    while running:
        try:
            data, addr = in_sock.recvfrom(65535)
        except Exception as e:
            print(f"[{now_ts()}] [RECV][ERROR] {e}\n{traceback.format_exc()}"); break

        src_ip, src_port = addr
        mid, apid, cc = parse_mid_apid_cc(data)
        head_hex16 = " ".join(f"{b:02X}" for b in data[:16])

        # 디버그: 현재 패킷의 MID/APID/CC 확인
        print(f"[RECV] {src_ip}:{src_port} len={len(data)} mid=0x{(mid or 0):04X} apid=0x{(apid or 0):04X} "
              f"cc={(cc if cc is not None else -1)} head={head_hex16}")
        print(f"[DEBUG] mid/apid check => mid=0x{(mid or 0):04X}, apid=0x{(apid or 0):04X}, cc={cc}")

        # SEND_TEXT일 때만 ID/TEXT 추출
        sid, stext = parse_id_text_if_send_text(data)
        if stext:
            if sid is not None:
                print(f"[TEXT] {sid}:{stext}")
            else:
                print(f"[TEXT] {stext}")

        text_bytes = (stext or "").encode('utf-8', errors='ignore')
        text_hex = to_hex(text_bytes)
        bits = bytes_to_bits(text_bytes)
        if bits:
            bits = "b:" + bits  # 엑셀 숫자 인식 방지

        # CSV(통일 스키마) 기록
        writer.writerow([
            now_ts(),                      # ts
            "sent",                        # direction
            (sid if sid is not None else ""),  # id
            (stext or ""),                 # text
            f"0x{(mid or 0):04X}",         # mid_hex
            f"0x{(apid or 0):04X}",        # apid_hex
            (cc if cc is not None else ""),# cc_dec
            len(data),                     # len
            src_ip, src_port,              # src_ip, src_port
            head_hex16,                    # head_hex16
            text_hex,                      # text_hex
            bits                           # bits
        ])

        # 포워딩
        try:
            out_sock.sendto(data, (UPLINK_DST_HOST, UPLINK_DST_PORT))
            print(f"[FWD ] -> {UPLINK_DST_HOST}:{UPLINK_DST_PORT} len={len(data)}")
        except Exception as e:
            print(f"[{now_ts()}] [SEND][ERROR] {e}\n{traceback.format_exc()}")

        if time.time() - last_flush >= 1.0:
            try: f.flush()
            except Exception: pass
            last_flush = time.time()

    try: f.flush(); f.close()
    except Exception: pass
    in_sock.close(); out_sock.close()
    print(f"[{now_ts()}] test1 stopped.")

if __name__ == "__main__":
    # python -u 추천 (버퍼링 방지)
    main()

