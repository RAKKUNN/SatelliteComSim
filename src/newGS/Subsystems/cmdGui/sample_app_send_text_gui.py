#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QLabel,
    QTextEdit, QPushButton, QMessageBox
)

ROOTDIR = Path(__file__).resolve().parent
CMDUTIL_PATH = (ROOTDIR / "../cmdUtil/cmdUtil").resolve()
LOG_PATH = ROOTDIR / "SentCommandLogs.txt"


class SendTextDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Send Text to Sample App")
        self.setGeometry(100, 100, 400, 200)

        layout = QVBoxLayout()

        self.label = QLabel("Enter message to send to SAMPLE_APP:")
        self.text_edit = QTextEdit()
        self.send_button = QPushButton("Send")

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.send_button)

        self.setLayout(layout)

        self.send_button.clicked.connect(self.send_command)

    def send_command(self):
        text = self.text_edit.toPlainText().strip()

        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter text before sending.")
            return

        # fixed packet values for SAMPLE_APP
        cmd = [
            str(CMDUTIL_PATH),
            "--host=127.0.0.1",
            "--port=50000",
            "--pktid=0x1882",
            "--cmdcode=2",
            f"--string=64:{text}"
        ]

        try:
            subprocess.run(cmd, check=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_msg = f"[{timestamp}] SAMPLE_APP SEND_TEXT: \"{text}\""

            # ✅ 파일 로그 기록
            with open(LOG_PATH, "a") as log_file:
                log_file.write(log_msg + "\n")

            # ✅ GroundSystem.py 로그로 출력되도록
            print(f"[CMD] {log_msg}")

            QMessageBox.information(self, "Success", "Message sent successfully!")

        except subprocess.CalledProcessError as e:
            print(f"[CMD] Error sending message: {e}")
            QMessageBox.critical(self, "Error", f"Failed to send:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SendTextDialog()
    window.show()
    sys.exit(app.exec_())

