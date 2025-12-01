#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_tlm_page.py (통일 스키마 대응판, 구분자 자동 감지, 호환성 개선)

- 읽는 CSV: newGS/log/sample_app_sent.csv, sample_app_recv.csv
- 공통 스키마(헤더):
  ts,direction,id,text,mid_hex,apid_hex,cc_dec,len,src_ip,src_port,head_hex16,text_hex,bits
- 매칭 조건:
  Sent: direction="sent" AND mid_hex==0x1882 AND cc_dec==3
  Recv: direction="recv" AND mid_hex==0x08A9
- BER 계산: 길이 다르면 짧은 쪽 기준(Partial)
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QLabel, QMessageBox, QHBoxLayout, QWidget
)

# 프로젝트 루트(newGS) 기준 경로
PROJECT_ROOT = Path(__file__).resolve().parents[2]   # .../newGS
LOG_DIR = PROJECT_ROOT / "log"
SENT_CSV = LOG_DIR / "sample_app_sent.csv"
RECV_CSV = LOG_DIR / "sample_app_recv.csv"

DARK_ORANGE_COLOR = QColor(255, 140, 0)
DISPLAY_TS_FMT = "%Y-%m-%d %H:%M:%S"

def _read_csv_rows(csv_path: Path):
    """콤마/탭/세미콜론 구분자 자동 감지 후 DictReader로 읽기."""
    rows = []
    if not csv_path.exists():
        print(f"[WARN] CSV not found: {csv_path}")
        return rows
    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except Exception:
                dialect = csv.excel  # 기본 콤마
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"[ERROR] read csv {csv_path}: {e}")
    return rows

class SampleAppTelemetryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sample App Telemetry Metrics")
        self.setMinimumSize(1150, 600)

        main_layout = QVBoxLayout(self)
        lbl = QLabel(
            "Sample App 전송·수신 매칭 결과 (ID 기준)\n"
            "- 통일 스키마 CSV(log/)를 읽어 BER 및 상태를 계산합니다.\n"
            "- 송수신 비트열 길이가 다르면 짧은 쪽 기준(Partial)으로 BER 계산."
        )
        main_layout.addWidget(lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Sent Timestamp", "Sent Message",
            "Recv Timestamp", "Recv Message", "RTT (ms)",
            "Status", "BER (%)", "Attack Type"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for col_idx in [1, 2, 3, 4, 8]:
            self.table.horizontalHeader().setSectionResizeMode(col_idx, QHeaderView.Interactive)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table, stretch=1)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_refresh = QPushButton("새로고침")
        self.btn_refresh.clicked.connect(self.refresh_data)
        self.btn_reset = QPushButton("기록 초기화")
        self.btn_reset.clicked.connect(self.reset_all_data)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_reset)
        main_layout.addWidget(btn_widget)

        # 경로 디버그
        print(f"[INFO] SENT_CSV={SENT_CSV.resolve()}")
        print(f"[INFO] RECV_CSV={RECV_CSV.resolve()}")

        self.refresh_data()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)

    def _parse_ts(self, s: str):
        if not s:
            return None
        try:
            return datetime.strptime(s, DISPLAY_TS_FMT)
        except Exception:
            return None

    def refresh_data(self):
        print("[INFO] Refreshing telemetry data...")

        sent_rows = _read_csv_rows(SENT_CSV)
        recv_rows = _read_csv_rows(RECV_CSV)
        print(f"[DEBUG] loaded rows: sent={len(sent_rows)}, recv={len(recv_rows)}")

        sent = {}  # id -> dict(ts, text, bits)
        recv = {}

        # Sent 필터: direction="sent", mid=0x1882, cc=3
        for row in sent_rows:
            try:
                if row.get("direction") != "sent":
                    continue
                if (row.get("mid_hex", "").lower() != "0x1882"):
                    continue
                cc_s = str(row.get("cc_dec", "")).strip()
                if cc_s != "3":
                    continue
                sid = (row.get("id", "") or "").strip()
                if not sid:
                    continue
                bits_raw = (row.get("bits", "") or "")
                # Python 3.8 호환: removeprefix 대신 replace 1회
                if bits_raw.startswith("b:"):
                    bits_clean = bits_raw.replace("b:", "", 1)
                else:
                    bits_clean = bits_raw
                sent[sid] = {
                    "ts": self._parse_ts(row.get("ts", "")),
                    "text": row.get("text", ""),
                    "bits": bits_clean
                }
            except Exception:
                continue

        # Recv 필터: direction="recv", mid=0x08A9
        for row in recv_rows:
            try:
                if row.get("direction") != "recv":
                    continue
                if (row.get("mid_hex", "").lower() != "0x08a9"):
                    continue
                sid = (row.get("id", "") or "").strip()
                if not sid:
                    continue
                bits_raw = (row.get("bits", "") or "")
                if bits_raw.startswith("b:"):
                    bits_clean = bits_raw.replace("b:", "", 1)
                else:
                    bits_clean = bits_raw
                recv[sid] = {
                    "ts": self._parse_ts(row.get("ts", "")),
                    "text": row.get("text", ""),
                    "bits": bits_clean
                }
            except Exception:
                continue

        # 매칭 및 표시
        def _sort_key(k: str):
            try:
                return int(k)
            except Exception:
                return 1 << 60

        ids = sorted(set(sent.keys()) | set(recv.keys()), key=_sort_key)
        self.table.setRowCount(0)
        self.table.setRowCount(len(ids))

        for row_idx, sid in enumerate(ids):
            s = sent.get(sid)
            r = recv.get(sid)

            # ID
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(sid)))

            # Sent TS/Text
            s_ts = s["ts"].strftime(DISPLAY_TS_FMT) if s and s.get("ts") else "-"
            s_text = s.get("text", "") if s else "-"
            self.table.setItem(row_idx, 1, QTableWidgetItem(s_ts))
            self.table.setItem(row_idx, 2, QTableWidgetItem(s_text))

            # Recv TS/Text
            r_ts = r["ts"].strftime(DISPLAY_TS_FMT) if r and r.get("ts") else "-"
            r_text = r.get("text", "") if r else "-"
            self.table.setItem(row_idx, 3, QTableWidgetItem(r_ts))
            self.table.setItem(row_idx, 4, QTableWidgetItem(r_text))

            # RTT
            item_rtt = QTableWidgetItem("-")
            if s and r and s.get("ts") and r.get("ts"):
                try:
                    delta_ms = int((r["ts"] - s["ts"]).total_seconds() * 1000)
                    item_rtt.setText(str(delta_ms))
                except Exception:
                    item_rtt.setText("Calc Error")
            self.table.setItem(row_idx, 5, item_rtt)

            # BER & Status
            ber_display = "-"
            status = "UNKNOWN"
            status_color = Qt.black

            if not r:
                status = "LOST"
                status_color = Qt.blue
            else:
                sbits = s.get("bits", "") if s else ""
                rbits = r.get("bits", "") if r else ""
                if sbits and rbits:
                    n = min(len(sbits), len(rbits))
                    partial = (len(sbits) != len(rbits))
                    if n > 0:
                        errors = sum(1 for i in range(n) if sbits[i] != rbits[i])
                        ber = errors / n
                        ber_display = f"{ber*100:.2f}" + (" (Partial)" if partial else "")
                        if ber == 0.0:
                            status = "OK"
                            status_color = Qt.darkGreen
                        else:
                            status = "CORRUPTED (BER)"
                            status_color = DARK_ORANGE_COLOR
                    else:
                        status = "RECEIVED (No Bits)"
                        status_color = Qt.darkGray
                else:
                    status = "RECEIVED (Partial Data for BER)"
                    status_color = Qt.darkGray

            self.table.setItem(row_idx, 7, QTableWidgetItem(ber_display))
            item_status = QTableWidgetItem(status)
            item_status.setForeground(status_color)
            self.table.setItem(row_idx, 6, item_status)

            # Attack Type: 현재 통일 스키마에 없음 → "-"
            self.table.setItem(row_idx, 8, QTableWidgetItem("-"))

        self.table.resizeRowsToContents()
        self.table.scrollToBottom()

    def reset_all_data(self):
        reply = QMessageBox.question(
            self,
            "초기화 확인",
            f"송신·수신 기록을 모두 삭제하시겠습니까?\n\n"
            f"송신: {SENT_CSV}\n수신: {RECV_CSV}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        header = [
            "ts","direction","id","text","mid_hex","apid_hex","cc_dec","len",
            "src_ip","src_port","head_hex16","text_hex","bits"
        ]
        try:
            for p in (SENT_CSV, RECV_CSV):
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(header)
            self.refresh_data()
            QMessageBox.information(self, "초기화 완료", "송수신 기록이 초기화되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "초기화 오류", f"파일 초기화 중 오류 발생:\n{e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = SampleAppTelemetryDialog()
    dlg.show()
    sys.exit(app.exec_())

