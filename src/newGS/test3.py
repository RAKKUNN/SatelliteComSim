#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket, struct, csv
from pathlib import Path
from datetime import datetime

LISTEN_IP, LISTEN_PORT = "0.0.0.0", 8890

# ---- 필터: SAMPLE_APP 텍스트 텔레메트리 후보 ----
FILTER_SID = {0x08A9, 0x1882}   # Stream ID로 보이는 값들
FILTER_APID = {0x0882, 0x08A9}  # APID로 보이는 값들

ROOTDIR = Path(__file__).resolve().parent
LOG_DIR = ROOTDIR / "log"; LOG_DIR.mkdir(parents=True, exist_ok=True)
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

def now_ts(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_csv_header(p, hdr):
    if (not p.exists()) or p.stat().st_size == 0:
        with open(p, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(hdr)

def to_hex(b): return "".join(f"{x:02X}" for x in b)
def bytes_to_bits(b): return "".join(f"{x:08b}" for x in b)

def parse_ccsds_header(pkt):
    if len(pkt) < 6: return None
    (sid, seq, length) = struct.unpack(">HHH", pkt[:6])
    apid = sid & 0x07FF
    return {"sid": sid, "apid": apid, "seq": seq, "len": length, "total_len": length + 7}

def is_sample_text(hdr):
    sid = hdr["sid"]; apid = hdr["apid"]
    return (sid in FILTER_SID) or (apid in FILTER_APID)

def extract_text(pkt: bytes) -> str:
    """
    SAMPLE_APP Text TLM을 두 포맷으로 시도:
    A) [12:14]=TextLen, [14:]=Text(최대128)
    B) [8: ] 문자열 (예: "ID:message")
    """
    # A 포맷
    if len(pkt) >= 14:
        try:
            text_len = (pkt[12] << 8) | pkt[13]
            text_raw = pkt[14:14+min(128, len(pkt)-14)]
            text = text_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            # text_len 보정
            if text_len > len(text):
                text_len = len(text)
            if text:
                return text[:text_len] if text_len else text
        except Exception:
            pass
    # B 포맷
    if len(pkt) > 8:
        try:
            text = pkt[8:].replace(b"\x00", b"").decode("utf-8", errors="ignore")
            # 너무 지저분하면 간단히 ':' 포함 여부로 거르기
            if ":" in text:
                return text.strip()
        except Exception:
            pass
    return ""

def split_id_text(text: str):
    sid = ""
    body = text
    parts = text.split(":", 1)
    if len(parts) == 2 and parts[0].isdigit():
        sid, body = parts[0], parts[1]
    return sid, body

def main():
    ensure_csv_header(RECV_CSV, [
        "ts","direction","id","text","sid_hex","apid_hex","cc_dec","len",
        "src_ip","src_port","head_hex16","text_hex","bits"
    ])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((LISTEN_IP, LISTEN_PORT))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)

    print(f"[test3] Listening from test4 on {LISTEN_IP}:{LISTEN_PORT} ...")
    print(f"[test3] Showing only SAMPLE_APP Text TLM (sid in {sorted(FILTER_SID)}, apid in {sorted(FILTER_APID)})")

    while True:
        data, addr = sock.recvfrom(4096)
        src_ip, src_port = addr
        hdr = parse_ccsds_header(data)
        if not hdr: 
            continue

        # cc (function code 추정)
        cc = data[6] if len(data) > 6 else None
        head_hex16 = " ".join(f"{b:02X}" for b in data[:16])

        # SAMPLE_APP 텍스트만 통과
        if not is_sample_text(hdr):
            continue

        # 텍스트 추출
        text = extract_text(data)
        sid_str, text_body = split_id_text(text)

        # 콘솔 출력
        print(f"[test3] [TEXT] {now_ts()} sid=0x{hdr['sid']:04X} apid=0x{hdr['apid']:04X} cc={(cc if cc is not None else -1)} text={text!r}")

        # CSV 기록
        text_bytes = text_body.encode("utf-8", errors="ignore")
        text_hex   = to_hex(text_bytes)
        bits = bytes_to_bits(text_bytes)
        if bits: bits = "b:" + bits

        with open(RECV_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                now_ts(), "recv", sid_str, text_body,
                f"0x{hdr['sid']:04X}", f"0x{hdr['apid']:04X}",
                (cc if cc is not None else ""), len(data),
                src_ip, src_port, head_hex16, text_hex, bits
            ])

if __name__ == "__main__":
    main()

