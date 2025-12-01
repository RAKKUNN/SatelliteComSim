#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import socket
from datetime import datetime

from gnuradio import gr, blocks
try:
    from gnuradio import network
    HAVE_NETWORK = True
except Exception:
    HAVE_NETWORK = False

# ---- 필터 설정: SAMPLE_APP 텍스트 텔레메트리 후보 (환경별 차이 흡수) ----
FILTER_SID = {0x08A9, 0x1882}   # Stream ID로 보이는 값들
FILTER_APID = {0x0882, 0x08A9}  # APID로 보이는 값들

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def parse_hdr(b: bytes):
    """CCSDS 기본 헤더 파싱: sid(2), seq(2), len(2)"""
    sid = apid = cc = None
    if len(b) >= 2:
        sid = (b[0] << 8) | b[1]
        apid = sid & 0x07FF
    if len(b) > 6:
        cc = b[6]
    head16 = " ".join(f"{x:02X}" for x in b[:16])
    return sid, apid, cc, head16

def looks_like_sample_text(pkt: bytes) -> bool:
    """SAMPLE_APP 텍스트 텔레메트리 패킷인지 판단"""
    sid, apid, cc, _ = parse_hdr(pkt)
    if sid in FILTER_SID or (apid is not None and apid in FILTER_APID):
        return True
    return False

def preview_text(pkt: bytes) -> str:
    """텍스트 미리보기 (두 가지 포맷 모두 시도)"""
    # 포맷 A: [12:14]=TextLen, [14:]=Text[최대128]
    if len(pkt) >= 14:
        try:
            tlen = (pkt[12] << 8) | pkt[13]
            raw = pkt[14:14+min(128, len(pkt)-14)]
            t = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
            if t:
                return t[:40]
        except Exception:
            pass
    # 포맷 B: [8: ]부터 문자열 가정 (예: "ID:message")
    if len(pkt) > 8:
        raw = pkt[8:]
        try:
            t = raw.replace(b"\x00", b"").decode("utf-8", errors="ignore")
            # 너무 지저분하면 간단히 콜론 패턴이 있는지 확인
            if ":" in t:
                return t[:40]
        except Exception:
            pass
    return ""

class pdu_tap(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(self, name="pdu_tap", in_sig=None, out_sig=None)
        self.message_port_register_in(gr.pmt.intern("pdus_in"))
        self.message_port_register_out(gr.pmt.intern("pdus_out"))
        self.set_msg_handler(gr.pmt.intern("pdus_in"), self.handle_pdu)

    def handle_pdu(self, pdu):
        vec  = gr.pmt.cdr(pdu)
        blob = bytes(bytearray(gr.pmt.u8vector_elements(vec)))
        sid, apid, cc, head16 = parse_hdr(blob)

        # (필수) 유입 1줄 요약
        print(f"[test4] [ANY] {now()} len={len(blob)} sid=0x{(sid or 0):04X} apid=0x{(apid or 0):04X} cc={(cc if cc is not None else -1)}")

        # SAMPLE_APP 후보만 상세 출력
        if looks_like_sample_text(blob):
            txt = preview_text(blob)
            print(f"[test4] [IN ] head16={head16}")
            if txt:
                print(f"[test4] [IN ] text='{txt}'")
            print(f"[test4] [FWD] -> UDP 127.0.0.1:8890 len={len(blob)}\n")

        # 항상 포워딩
        self.message_port_pub(gr.pmt.intern("pdus_out"), pdu)

class DownlinkUdpRelay(gr.top_block):
    def __init__(self, listen_ip="0.0.0.0", listen_port=1235, out_ip="127.0.0.1", out_port=8890):
        gr.top_block.__init__(self, "DownlinkUdpRelay")
        if HAVE_NETWORK:
            self.udp_in  = network.socket_pdu("UDP_SERVER", listen_ip, str(listen_port), 1472, False)
            self.udp_out = network.socket_pdu("UDP_CLIENT", out_ip,    str(out_port),    1472, False)
        else:
            self.udp_in  = blocks.socket_pdu("UDP_SERVER", listen_ip, str(listen_port), 1472, False)
            self.udp_out = blocks.socket_pdu("UDP_CLIENT", out_ip,    str(out_port),    1472, False)
        self.tap = pdu_tap()
        self.msg_connect(self.udp_in, "pdus", self.tap, "pdus_in")
        self.msg_connect(self.tap, "pdus_out", self.udp_out, "pdus")

def main():
    # 포트 점유 체크(친절모드)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", 1235))
    except OSError:
        print("[test4] ERROR: UDP 1235 already in use. 기존 리스너 종료 필요.")
        return
    finally:
        s.close()

    tb = DownlinkUdpRelay("0.0.0.0", 1235, "127.0.0.1", 8890)
    print(f"[test4] Listening cFS UDP on 0.0.0.0:1235 ...")
    print(f"[test4] Forwarding to 127.0.0.1:8890 (detail only SAMPLE_APP)")
    tb.start()
    print("[test4] started.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        tb.stop(); tb.wait()
        print("[test4] stopped.")

if __name__ == "__main__":
    main()

