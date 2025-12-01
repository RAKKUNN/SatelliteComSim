#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test2.py — Uplink GNURadio PDU UDP relay with space-channel (payload-only BER) and debug logs

Path:
  test1 (UDP -> 8600)  →  [test2.py]  →  cFS CI_LAB (UDP 1234)

- UDP datagram 경계 = PDU 경계 그대로 유지
- IN/FWD 로그(길이, 헤더16, MID/APID/CC, 텍스트 프리뷰) 출력
- 우주환경(지연/지터 + BER) 주입:
  * 기본: 'payload-only' 모드 — SAMPLE_APP Text TLM(0x08A9)의 텍스트 바이트 영역에만 BER 적용
  * 헤더/식별자(MID/APID/CC 등)는 보호(무변조)
  * 지연/지터는 전체 PDU에 동일하게 적용
  * --full-ber 옵션을 주면 전체 바이트에 BER 적용(테스트용)

- GroundSystem 연동:
  * 실행 시 test2_config.json을 자동 로드(또는 환경변수 TEST2_CONFIG로 경로 지정)
  * 런타임 제어용 UDP 컨트롤 서버(기본 127.0.0.1:9696)로 파라미터 실시간 갱신
"""

import os
import json
import time
import random
import heapq
import threading
import argparse
import socket
from datetime import datetime
from typing import Optional, Tuple
from struct import unpack

from gnuradio import gr, blocks
import pmt


# ---------------------- 설정 파일 로딩 ----------------------
def load_config_json():
    """
    우선순위:
    1) 환경변수 TEST2_CONFIG 지정 경로
    2) 스크립트 디렉토리의 'test2_config.json'
    없으면 None
    """
    candidates = []
    env_p = os.environ.get("TEST2_CONFIG")
    if env_p:
        candidates.append(env_p)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "test2_config.json"))

    for p in candidates:
        try:
            if p and os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return None


def apply_config_overrides(args, cfg: dict):
    """
    JSON의 키가 있으면 argparse 값 위에 덮어씀
    """
    if not cfg:
        return args

    def setv(k, dst):
        if k in cfg:
            setattr(args, dst, cfg[k])

    setv("listen_ip", "listen_ip")
    setv("listen_port", "listen_port")
    setv("dst_ip", "dst_ip")
    setv("dst_port", "dst_port")
    setv("mtu", "mtu")

    setv("base_delay_ms", "base_delay_ms")
    setv("jitter_ms", "jitter_ms")
    setv("ber", "ber")
    setv("seed", "seed")

    # mode: "payload_only" / "full"
    if "mode" in cfg:
        m = str(cfg["mode"]).lower().strip()
        if m == "full":
            args.full_ber = True
            args.payload_only = False
        else:
            args.full_ber = False
            args.payload_only = True

    # SAMPLE_APP 텍스트 오프셋
    setv("tlm08a9_len_off", "tlm08a9_len_off")
    setv("tlm08a9_text_off", "tlm08a9_text_off")
    setv("tlm08a9_text_max", "tlm08a9_text_max")

    # 컨트롤 서버
    setv("ctrl_bind_ip", "ctrl_bind_ip")
    setv("ctrl_port", "ctrl_port")

    return args


# ---------------------- 공통 유틸 ----------------------
def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_mid_apid_cc(raw_bytes: bytes):
    """
    MID(16b BE), APID(하위 11b), CC(byte6) 추출. 부족하면 None.
    """
    mid = apid = cc = None
    if len(raw_bytes) >= 2:
        mid = (raw_bytes[0] << 8) | raw_bytes[1]
        apid = mid & 0x07FF
    if len(raw_bytes) > 6:
        cc = raw_bytes[6]
    return mid, apid, cc


def head_hex16(raw_bytes: bytes):
    return " ".join(f"{b:02X}" for b in raw_bytes[:16])


def ascii_preview(raw_bytes: bytes, n=64):
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw_bytes[:n])


def be16(b: bytes) -> int:
    return unpack(">H", b)[0]


def extract_mid(pkt: bytes) -> int:
    return be16(pkt[0:2]) if len(pkt) >= 2 else -1


def text_region_for_tlm_08a9(pkt: bytes,
                             len_off=12, text_off=14, text_max=128) -> Optional[Tuple[int, int]]:
    """
    SAMPLE_APP Text TLM (MID=0x08A9) 전용:
    [12:14]=TextLen(2B BE), [14:...]=Text(NULL 종료, 최대 128)
    반환: (start, end) 또는 None
    """
    if len(pkt) < text_off:
        return None
    try:
        text_len = be16(pkt[len_off:len_off+2])
    except Exception:
        return None
    text_len = max(0, min(int(text_len), int(text_max)))
    start = int(text_off)
    end = min(len(pkt), start + text_len)
    return (start, end) if end > start else None


def flip_bits_inplace(buf: bytearray, ber: float, rng: random.Random, start: int = 0, end: Optional[int] = None):
    """buf[start:end] 범위에서 비트 오류 주입"""
    if ber <= 0.0:
        return
    L = len(buf)
    s = max(0, start)
    e = L if end is None else max(0, min(L, end))
    if s >= e:
        return
    for i in range(s, e):
        b = buf[i]
        # 각 비트 독립 플립
        for bit in range(8):
            if rng.random() < ber:
                b ^= (1 << bit)
        buf[i] = b


# ---------------------- 로거 블록 ----------------------
class PduLogger(gr.basic_block):
    """
    입력: message port "pdus" (pmt.cons(meta, u8vector))
    출력: message port "pdus" (동일 PDU 패스스루)
    label로 IN/FWD 구분해서 로그 출력
    """
    def __init__(self, label="IN"):
        gr.basic_block.__init__(self,
                                name=f"PduLogger({label})",
                                in_sig=None,
                                out_sig=None)
        self.label = label
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))

    def _handler(self, msg):
        try:
            meta = pmt.to_python(pmt.car(msg))
            vec = pmt.cdr(msg)
            data = bytes(bytearray(pmt.u8vector_elements(vec)))
        except Exception:
            meta = {}
            data = b""

        mid, apid, cc = parse_mid_apid_cc(data)
        h16 = head_hex16(data)
        preview = ascii_preview(data)

        ip = meta.get("ip", "") if isinstance(meta, dict) else ""
        port = meta.get("port", "") if isinstance(meta, dict) else ""

        print(f"[{self.label}] {now_ts()} len={len(data)} mid=0x{(mid or 0):04X} apid=0x{(apid or 0):04X} cc={(cc if cc is not None else -1)}")
        if ip or port:
            print(f"[{self.label}] src={ip}:{port}")
        print(f"[{self.label}] head16={h16}")
        print(f"[{self.label}] text='{preview}'")

        # 그대로 패스스루
        self.message_port_pub(pmt.intern("pdus"), msg)


# ---------------------- 우주환경 블록 ----------------------
class PduSpaceChannel(gr.basic_block):
    """
    우주환경(지연/지터 + BER) 모델을 PDU에 적용하는 블록.
    - 기본: payload-only BER (SAMPLE_APP Text TLM 0x08A9 텍스트 바이트에만 BER)
    - --full-ber 사용 시 전체 바이트에 BER
    - 지연/지터는 전체 PDU에 적용
    """
    def __init__(self,
                 base_delay_ms: float = 0.0,
                 jitter_ms: float = 0.0,
                 ber: float = 0.0,
                 seed: int = 0xBEEF,
                 payload_only: bool = True,
                 tlm08a9_len_off: int = 12,
                 tlm08a9_text_off: int = 14,
                 tlm08a9_text_max: int = 128):
        gr.basic_block.__init__(self,
                                name="PduSpaceChannel",
                                in_sig=None,
                                out_sig=None)
        # 파라미터
        self.base_delay_ms = float(base_delay_ms)
        self.jitter_ms = float(jitter_ms)
        self.ber = float(ber)
        self.rng = random.Random(int(seed))
        self.payload_only = bool(payload_only)
        self.len_off = int(tlm08a9_len_off)
        self.text_off = int(tlm08a9_text_off)
        self.text_max = int(tlm08a9_text_max)

        # 내부 락 (런타임 세터 안전화)
        self._lock = threading.Lock()

        # PDU 포트
        self.message_port_register_in(pmt.intern("pdus"))
        self.set_msg_handler(pmt.intern("pdus"), self._handler)
        self.message_port_register_out(pmt.intern("pdus"))

        # 전송 예약 큐 (time_ns, (meta, bytes))
        self._send_heap = []
        self._stop = False
        self._tx_thread = threading.Thread(target=self._tx_worker, daemon=True)
        self._tx_thread.start()

    # 런타임 파라미터 세터
    def set_params(self, **kw):
        with self._lock:
            if "base_delay_ms" in kw: self.base_delay_ms = float(kw["base_delay_ms"])
            if "jitter_ms"     in kw: self.jitter_ms     = float(kw["jitter_ms"])
            if "ber"           in kw: self.ber           = float(kw["ber"])
            if "seed"          in kw: self.rng.seed(int(kw["seed"]))
            if "payload_only"  in kw: self.payload_only  = bool(kw["payload_only"])
            if "tlm08a9_len_off"  in kw: self.len_off   = int(kw["tlm08a9_len_off"])
            if "tlm08a9_text_off" in kw: self.text_off  = int(kw["tlm08a9_text_off"])
            if "tlm08a9_text_max" in kw: self.text_max  = int(kw["tlm08a9_text_max"])

    def _now_ns(self) -> int:
        return time.monotonic_ns()

    def _sleep_until_ns(self, t_ns: int):
        while True:
            diff = t_ns - self._now_ns()
            if diff <= 0:
                break
            time.sleep(min(diff / 1e9, 0.001))

    def _schedule_send(self, meta_py: dict, data_bytes: bytes, delay_s: float):
        send_t = self._now_ns() + int(max(0.0, delay_s) * 1e9)
        heapq.heappush(self._send_heap, (send_t, (meta_py, data_bytes)))

    def _tx_worker(self):
        while not self._stop:
            if not self._send_heap:
                time.sleep(0.0005)
                continue
            t_ns, payload = self._send_heap[0]
            self._sleep_until_ns(t_ns)
            # 가능한 만큼 전송
            while self._send_heap and self._send_heap[0][0] <= self._now_ns():
                _, (meta_py, data_bytes) = heapq.heappop(self._send_heap)
                # meta_py(dict)와 data_bytes(bytes)로 PDU 만들기
                meta_pmt = pmt.to_pmt(meta_py if isinstance(meta_py, dict) else {})
                vec = pmt.init_u8vector(len(data_bytes), list(data_bytes))
                out_msg = pmt.cons(meta_pmt, vec)
                self.message_port_pub(pmt.intern("pdus"), out_msg)

    def _handler(self, msg):
        # PDU unpack
        try:
            meta = pmt.to_python(pmt.car(msg))
            vec = pmt.cdr(msg)
            data = bytes(bytearray(pmt.u8vector_elements(vec)))
        except Exception:
            meta = {}
            data = b""

        # BER 적용
        modified = bytearray(data)

        cur_ber = self.ber
        if cur_ber > 0.0:
            if self.payload_only:
                mid = extract_mid(modified)
                if mid == 0x08A9:
                    region = text_region_for_tlm_08a9(modified,
                                                      len_off=self.len_off,
                                                      text_off=self.text_off,
                                                      text_max=self.text_max)
                    if region:
                        s, e = region
                        flip_bits_inplace(modified, cur_ber, self.rng, start=s, end=e)
                # 다른 MID에 대한 payload-only 매핑을 추가하려면 여기 분기 추가
            else:
                # 전체 바이트 BER
                flip_bits_inplace(modified, cur_ber, self.rng, start=0, end=None)

        # 지연/지터 계산 (락 안에서 읽을 필요는 없음: 단순 읽기)
        base = self.base_delay_ms / 1000.0
        jitter = self.jitter_ms / 1000.0
        if jitter > 0.0:
            # 대략 3시그마 내 분포
            delay_s = max(0.0, self.rng.gauss(base, jitter / 3.0))
        else:
            delay_s = max(0.0, base)

        # 전송 예약
        self._schedule_send(meta, bytes(modified), delay_s)

    def stop(self):
        # GNU Radio에서 호출될 수 있는 정지 훅
        self._stop = True
        try:
            self._tx_thread.join(timeout=1.0)
        except Exception:
            pass
        return True


# ---------------------- 토폴로지 ----------------------
class UplinkUdpRelay(gr.top_block):
    def __init__(self,
                 listen_ip="0.0.0.0", listen_port=8600,
                 dst_ip="127.0.0.1", dst_port=1234,
                 mtu=1472, verbose=True,
                 base_delay_ms=0.0, jitter_ms=0.0, ber=0.0, seed=0xBEEF,
                 payload_only=True,
                 tlm08a9_len_off=12, tlm08a9_text_off=14, tlm08a9_text_max=128,
                 full_ber=False,
                 ctrl_bind_ip="127.0.0.1", ctrl_port=9696):
        super().__init__()

        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.mtu = mtu
        self.verbose = verbose

        self.ctrl_bind_ip = ctrl_bind_ip
        self.ctrl_port = int(ctrl_port)
        self._ctrl_sock = None
        self._ctrl_thr = None
        self._stop_ctrl = False

        # UDP → PDU (수신: 서버모드)
        self.udp_in = blocks.socket_pdu("UDP_SERVER",
                                        self.listen_ip,
                                        str(self.listen_port),
                                        self.mtu,
                                        True)

        # 로거(수신측)
        self.log_in = PduLogger("IN ")

        # 우주환경 블록 (payload-only 기본)
        self.space = PduSpaceChannel(
            base_delay_ms=base_delay_ms,
            jitter_ms=jitter_ms,
            ber=ber,
            seed=seed,
            payload_only=(not full_ber) and payload_only,
            tlm08a9_len_off=tlm08a9_len_off,
            tlm08a9_text_off=tlm08a9_text_off,
            tlm08a9_text_max=tlm08a9_text_max,
        )

        # 로거(전송 전 확인)
        self.log_fwd = PduLogger("FWD")

        # PDU → UDP (송신: 클라이언트모드)
        self.udp_out = blocks.socket_pdu("UDP_CLIENT",
                                         self.dst_ip,
                                         str(self.dst_port),
                                         self.mtu,
                                         True)

        # 연결
        self.msg_connect(self.udp_in,  "pdus", self.log_in,  "pdus")
        self.msg_connect(self.log_in,  "pdus", self.space,   "pdus")
        self.msg_connect(self.space,   "pdus", self.log_fwd, "pdus")
        self.msg_connect(self.log_fwd, "pdus", self.udp_out, "pdus")

        if self.verbose:
            print(f"[test2] Listening UDP PDU on {self.listen_ip}:{self.listen_port}")
            print(f"[test2] Forwarding UDP PDU to {self.dst_ip}:{self.dst_port}")
            print(f"[test2] MTU={self.mtu}")
            mode = "payload-only BER" if ((not full_ber) and payload_only) else "full BER"
            print(f"[test2] Space channel: delay={base_delay_ms}ms±{jitter_ms}ms, BER={ber} ({mode})")

        # 컨트롤 서버 시작
        self._start_ctrl_server()

    def _start_ctrl_server(self):
        def worker():
            try:
                self._ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._ctrl_sock.bind((self.ctrl_bind_ip, self.ctrl_port))
                print(f"[CTRL] Listening on {self.ctrl_bind_ip}:{self.ctrl_port}")
                while not self._stop_ctrl:
                    self._ctrl_sock.settimeout(0.5)
                    try:
                        data, addr = self._ctrl_sock.recvfrom(65535)
                    except socket.timeout:
                        continue
                    try:
                        msg = json.loads(data.decode("utf-8", "ignore"))
                    except Exception:
                        continue
                    # 프로토콜: {"cmd":"set", "params":{...}} or {"cmd":"ping"}
                    if msg.get("cmd") == "ping":
                        try:
                            self._ctrl_sock.sendto(b'{"ok":true,"pong":1}', addr)
                        except Exception:
                            pass
                        continue

                    if msg.get("cmd") == "set":
                        params = msg.get("params", {})
                        # mode 해석
                        if "mode" in params:
                            m = str(params["mode"]).lower()
                            if m == "full":
                                self.space.set_params(payload_only=False)
                            else:
                                self.space.set_params(payload_only=True)
                        # 나머지 수치들
                        self.space.set_params(**params)
                        try:
                            self._ctrl_sock.sendto(b'{"ok":true}', addr)
                        except Exception:
                            pass
            except Exception as e:
                print("[CTRL] error:", e)

        self._ctrl_thr = threading.Thread(target=worker, daemon=True)
        self._ctrl_thr.start()

    def stop(self):
        # 컨트롤 스레드 정리
        self._stop_ctrl = True
        try:
            if self._ctrl_sock:
                self._ctrl_sock.close()
        except Exception:
            pass
        return super().stop()


# ---------------------- 엔트리포인트 ----------------------
def main():
    ap = argparse.ArgumentParser(description="GNURadio UDP PDU relay (uplink) with space-channel and debug logs")
    ap.add_argument("--listen-ip", default="0.0.0.0", help="UDP listen IP (default: 0.0.0.0)")
    ap.add_argument("--listen-port", type=int, default=8600, help="UDP listen port (default: 8600)")
    ap.add_argument("--dst-ip", default="127.0.0.1", help="Destination IP (default: 127.0.0.1)")
    ap.add_argument("--dst-port", type=int, default=1234, help="Destination port (default: 1234)")
    ap.add_argument("--mtu", type=int, default=1472, help="UDP PDU MTU (default: 1472)")
    ap.add_argument("--quiet", action="store_true", help="Less logs")

    # Space channel params
    ap.add_argument("--base-delay-ms", type=float, default=0.0, help="Base one-way delay in ms (default: 0)")
    ap.add_argument("--jitter-ms", type=float, default=0.0, help="Jitter stdev approx in ms (default: 0)")
    ap.add_argument("--ber", type=float, default=0.0, help="Bit error rate (default: 0)")
    ap.add_argument("--seed", type=int, default=0xBEEF, help="RNG seed (default: 0xBEEF)")

    # Payload-only mapping (SAMPLE_APP Text TLM 0x08A9)
    ap.add_argument("--payload-only", action="store_true",
                    help="Apply BER only to SAMPLE_APP Text payload (default mode if --full-ber not set)")
    ap.add_argument("--full-ber", action="store_true",
                    help="Apply BER to entire PDU bytes (overrides payload-only)")

    ap.add_argument("--tlm08a9-len-off", type=int, default=12, help="Text length field offset (BE16)")
    ap.add_argument("--tlm08a9-text-off", type=int, default=14, help="Text start offset")
    ap.add_argument("--tlm08a9-text-max", type=int, default=128, help="Max text length")

    # Control server (for runtime updates from GroundSystem)
    ap.add_argument("--ctrl-bind-ip", default="127.0.0.1", help="Control UDP bind IP (default: 127.0.0.1)")
    ap.add_argument("--ctrl-port", type=int, default=9696, help="Control UDP port (default: 9696)")

    args = ap.parse_args()

    # 설정 파일 오버라이드 적용
    cfg = load_config_json()
    args = apply_config_overrides(args, cfg)

    # payload-only 기본값: True (사용자가 --full-ber 주면 전체 BER)
    payload_only_effective = True
    if args.full_ber:
        payload_only_effective = False
    elif args.payload_only:
        payload_only_effective = True

    tb = UplinkUdpRelay(
        listen_ip=args.listen_ip,
        listen_port=args.listen_port,
        dst_ip=args.dst_ip,
        dst_port=args.dst_port,
        mtu=args.mtu,
        verbose=not args.quiet,
        base_delay_ms=args.base_delay_ms,
        jitter_ms=args.jitter_ms,
        ber=args.ber,
        seed=args.seed,
        payload_only=payload_only_effective,
        tlm08a9_len_off=args.tlm08a9_len_off,
        tlm08a9_text_off=args.tlm08a9_text_off,
        tlm08a9_text_max=args.tlm08a9_text_max,
        full_ber=args.full_ber,
        ctrl_bind_ip=args.ctrl_bind_ip,
        ctrl_port=args.ctrl_port
    )
    tb.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    tb.stop(); tb.wait()


if __name__ == "__main__":
    main()

