#!/usr/bin/env python3

import csv
import pickle
import shlex
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QDialog, QHeaderView, QPushButton,
                             QTableWidgetItem)

from MiniCmdUtil import MiniCmdUtil
from UiCommandsystemdialog import UiCommandsystemdialog

ROOTDIR = Path(sys.argv[0]).resolve().parent


class CommandSystem(QDialog, UiCommandsystemdialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.move(800, 100)
        self.mcu = None

    def process_button_generic(self, idx):
        if cmd_page_is_valid[idx]:
            app_name = self.tbl_cmd_sys.item(idx, 0).text().strip()

            # ✅ Sample App 텍스트 GUI 호출
            if app_name in ["Sample App", "Sample App (CPU1)", "Sample App Text Send"]:
                gui_path = ROOTDIR / "sample_app_send_text_gui.py"
                subprocess.Popen(["python3", str(gui_path)])

                # ✔ 로그에 기록
                with open(ROOTDIR / "SentCommandLogs.txt", "a") as logf:
                    logf.write(f"[{datetime.now()}] GUI Opened for SAMPLE_APP Text Send (via Display Page)\n")
                return

            # 기본 명령 GUI 로직
            pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
            address = self.tbl_cmd_sys.item(idx, 2).text()
            launch_string = (
                f'python3 {ROOTDIR}/{cmdClass[idx]} '
                f'--title="{cmdPageDesc[idx]}" --pktid={pkt_id} '
                f'--file={cmdPageDefFile[idx]} --address="{address}" '
                f'--port={cmdPagePort[idx]} --endian={cmdPageEndian[idx]}'
            )
            cmd_args = shlex.split(launch_string)
            subprocess.Popen(cmd_args)

    @staticmethod
    def check_params(idx):
        pickle_file = f'{ROOTDIR}/ParameterFiles/{quick_param[idx]}'
        try:
            with open(pickle_file, 'rb') as pickle_obj:
                param_names = pickle.load(pickle_obj)[1]
            return len(param_names) > 0
        except IOError:
            return False

    def process_quick_button(self, idx):
        if cmd_page_is_valid[idx] and quick_indices[idx] >= 0:
            q_idx = quick_indices[idx]
            pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
            address = self.tbl_cmd_sys.item(idx, 2).text()

            # ✅ Sample App 텍스트 GUI (Quick Command 버튼 클릭 시)
            if subsys[q_idx] in ["Sample App", "Sample App Text Send"] and quick_cmd[q_idx] == "Send Text":
                gui_path = ROOTDIR / "sample_app_send_text_gui.py"
                subprocess.Popen(["python3", str(gui_path)])

                with open(ROOTDIR / "SentCommandLogs.txt", "a") as logf:
                    logf.write(f"[{datetime.now()}] GUI Opened for SAMPLE_APP Text Send (via Quick Command)\n")
                return

            # 파라미터가 필요한 경우
            if self.check_params(q_idx):
                launch_string = (
                    f'python3 {ROOTDIR}/Parameter.py '
                    f'--title="{subsys[q_idx]}" '
                    f'--descrip="{quick_cmd[q_idx]}" '
                    f'--idx={idx} --host="{address}" '
                    f'--port={quick_port[q_idx]} '
                    f'--pktid={pkt_id} --endian={quick_endian[q_idx]} '
                    f'--cmdcode={quick_code[q_idx]} --file={quick_param[q_idx]}'
                )
                cmd_args = shlex.split(launch_string)
                subprocess.Popen(cmd_args)
            else:
                self.mcu = MiniCmdUtil(address, quick_port[q_idx],
                                       quick_endian[q_idx], pkt_id,
                                       quick_code[q_idx])
                send_success = self.mcu.send_packet()
                print("Command sent successfully:", send_success)

    def closeEvent(self, event):
        if self.mcu:
            self.mcu.mm.close()
        super().closeEvent(event)


# Main
if __name__ == '__main__':
    cmd_def_file = "command-pages.txt"

    app = QApplication(sys.argv)
    command = CommandSystem()
    tbl = command.tbl_cmd_sys

    cmd_page_is_valid, cmdPageDesc, cmdPageDefFile, cmdPageAppid, \
    cmdPageEndian, cmdClass, cmdPageAddress, cmdPagePort = ([] for _ in range(8))

    i = 0
    with open(f"{ROOTDIR}/{cmd_def_file}") as cmdfile:
        reader = csv.reader(cmdfile, skipinitialspace=True)
        for cmdRow in reader:
            try:
                if not cmdRow[0].startswith('#'):
                    cmd_page_is_valid.append(True)
                    cmdPageDesc.append(cmdRow[0])
                    cmdPageDefFile.append(cmdRow[1])
                    cmdPageAppid.append(int(cmdRow[2], 16))
                    cmdPageEndian.append(cmdRow[3])
                    cmdClass.append(cmdRow[4])
                    cmdPageAddress.append(cmdRow[5])
                    cmdPagePort.append(int(cmdRow[6]))
                    i += 1
            except IndexError as e:
                print("IndexError:", e)
                print("This may be due to a formatting issue in command-pages.txt")

    for _ in range(i, 22):
        cmdPageAppid.append(0)
        cmd_page_is_valid.append(False)

    quick_def_file = 'quick-buttons.txt'
    subsys, subsys_file, quick_cmd, quick_code, quick_pkt_id, \
    quick_endian, quick_address, quick_port, quick_param, \
    quick_indices = ([] for _ in range(10))

    with open(f'{ROOTDIR}/{quick_def_file}') as subFile:
        reader = csv.reader(subFile)
        for fileRow in reader:
            if not fileRow[0].startswith('#'):
                subsys.append(fileRow[0])
                subsys_file.append(fileRow[1])
                quick_cmd.append(fileRow[2].strip())
                quick_code.append(fileRow[3].strip())
                quick_pkt_id.append(fileRow[4].strip())
                quick_endian.append(fileRow[5].strip())
                quick_address.append(fileRow[6].strip())
                quick_port.append(fileRow[7].strip())
                quick_param.append(fileRow[8].strip())

    for k, desc in enumerate(cmdPageDesc):
        if cmd_page_is_valid[k]:
            tbl.insertRow(k)
            for col, text in enumerate((desc, hex(cmdPageAppid[k]), cmdPageAddress[k])):
                tbl_item = QTableWidgetItem(text)
                tbl.setItem(k, col, tbl_item)

            tbl_btn = QPushButton("Display Page")
            tbl_btn.clicked.connect(lambda _, x=k: command.process_button_generic(x))
            tbl.setCellWidget(k, 3, tbl_btn)

            quick_idx = -1
            try:
                quick_idx = subsys.index(desc)
            except ValueError:
                pass
            else:
                quick_btn = QPushButton(quick_cmd[quick_idx])
                quick_btn.clicked.connect(lambda _, x=k: command.process_quick_button(x))
                tbl.setCellWidget(k, 4, quick_btn)

            quick_indices.append(quick_idx)

    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    tbl.horizontalHeader().setStretchLastSection(True)

    command.show()
    command.raise_()
    print('Command System started.')
    sys.exit(app.exec_())

