#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sample_app_send_text_gui.py

사용자 입력 텍스트를 SAMPLE_APP으로 전송한다.
ID는 test1이 기록하는 log/sample_app_sent.csv의 마지막 ID 다음 번호로 자동 할당한다.
전송 로그(csv 저장)는 test1.py/test3.py에서 처리한다.

- pktid(MID): 0x1882 (SAMPLE_APP_CMD_MID)
"""

import os  # ✅ 반드시 필요 (os.getenv 사용)
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import csv

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox
)

# 이 스크립트 파일이 위치한 디렉토리 (…/Subsystems/cmdGui)
ROOTDIR_GUI = Path(__file__).resolve().parent
PROJECT_ROOT = ROOTDIR_GUI.parent.parent     # …/newGS (test1.py, log/ 가 있는 위치)

# cmdUtil 경로 (…/Subsystems/cmdUtil/cmdUtil)
CMDUTIL_PATH = (ROOTDIR_GUI / "../cmdUtil/cmdUtil").resolve()

# SAMPLE_APP CMD MID
SAMPLE_APP_CMD_MID = "0x1882"

# ★ ID 추적용 CSV: test1이 쓰는 로그를 바라본다 (log/sample_app_sent.csv)
#   환경변수 GS_SENT_LOG로 오버라이드 가능
SENT_CSV_FILE_PATH = Path(
    os.getenv("GS_SENT_LOG", str(PROJECT_ROOT / "log" / "sample_app_sent.csv"))
)

class SendTextDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Send Text to Sample App (Auto ID from test1 log)")
        self.setGeometry(100, 100, 400, 250)

        layout = QVBoxLayout()
        self.label = QLabel("Enter message to send to SAMPLE_APP:")
        self.text_edit = QTextEdit()
        self.send_button = QPushButton("Send")
        self.debug_label = QLabel("Next ID will be: ?")

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.send_button)
        layout.addWidget(self.debug_label)
        self.setLayout(layout)

        self.send_button.clicked.connect(self.send_command)

        print(f"[INFO] GUI ROOTDIR: {ROOTDIR_GUI}")
        print(f"[INFO] Using SENT CSV (from test1): {SENT_CSV_FILE_PATH.resolve()}")

        last_id_from_csv = self._get_last_seq_id_from_csv()
        self.next_seq_id = last_id_from_csv + 1
        self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        print(f"[INFO] Next sequence ID initialized to: {self.next_seq_id}")

    def _get_last_seq_id_from_csv(self):
        max_id = 0
        resolved_path = SENT_CSV_FILE_PATH.resolve()
        print(f"[DEBUG] _get_last_seq_id_from_csv: Checking file at {resolved_path}")

        if SENT_CSV_FILE_PATH.exists() and SENT_CSV_FILE_PATH.is_file():
            if SENT_CSV_FILE_PATH.stat().st_size > 0:
                try:
                    with open(SENT_CSV_FILE_PATH, "r", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        if not reader.fieldnames or "id" not in reader.fieldnames:
                            return 0
                        for row in reader:
                            try:
                                cur = int(str(row.get("id", "0")).strip())
                                if cur > max_id:
                                    max_id = cur
                            except Exception:
                                continue
                except Exception as e_file:
                    print(f"[ERROR] Failed to read {resolved_path}: {e_file}. Start from 1.")
                    return 0
        return max_id

    def send_command(self):
        raw_text = self.text_edit.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Input Error", "Please enter text before sending.")
            return

        current_id_to_send = self.next_seq_id
        message = f"{current_id_to_send}:{raw_text}"

        self.next_seq_id += 1
        self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")

        full_text_bytes = message.encode("utf-8", errors="ignore")[:128]
        full_text_str   = full_text_bytes.decode("utf-8", errors="ignore")

        print(f"[DEBUG] Final message to send: {full_text_str!r} (ID: {current_id_to_send})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cmd = [
            str(CMDUTIL_PATH), "--host=127.0.0.1", "--port=50000",
            f"--pktid={SAMPLE_APP_CMD_MID}", "--cmdcode=3", f"--string=128:{full_text_str}"
        ]

        try:
            if not CMDUTIL_PATH.is_file():
                QMessageBox.critical(self, "Error", f"cmdUtil not found at:\n{CMDUTIL_PATH}")
                # ID 롤백
                self.next_seq_id -= 1
                self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
                return

            process_result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"[CMDUTIL STDOUT] {process_result.stdout}")
            if process_result.stderr:
                print(f"[CMDUTIL STDERR] {process_result.stderr}")

            print(f"[CMD] SENT: {message}")
            QMessageBox.information(self, "Success", f"Message sent as ID {current_id_to_send}")
            self.text_edit.clear()

        except subprocess.CalledProcessError as e:
            print(f"[CMD] Error sending message: {e}\nStdout: {e.stdout}\nStderr: {e.stderr}")
            QMessageBox.critical(self, "Error", f"Failed to send (CalledProcessError):\n{e}\n{e.stderr}")
            self.next_seq_id -= 1
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        except FileNotFoundError:
            print(f"[CMD] Error: cmdUtil not found at {CMDUTIL_PATH}")
            QMessageBox.critical(self, "Error", f"cmdUtil not found.\nCheck path: {CMDUTIL_PATH}")
            self.next_seq_id -= 1
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")
        except Exception as e_generic:
            print(f"[CMD] Generic error sending message: {e_generic}")
            QMessageBox.critical(self, "Error", f"Failed to send:\n{e_generic}")
            self.next_seq_id -= 1
            self.debug_label.setText(f"Next ID will be: {self.next_seq_id}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SendTextDialog()
    window.show()
    sys.exit(app.exec_())

