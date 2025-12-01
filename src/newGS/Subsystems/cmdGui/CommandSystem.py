#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CommandSystem.py

- GroundSystem 명령 GUI를 제공하는 모듈입니다.
- cFS로 명령을 전송할 수 있으며, Quick Command 기능도 포함합니다.

수정사항(2025-10-30):
- Sample App Text GUI 실행 분기 조건을 유연화(대소문자/공백/부가 라벨에 덜 민감).
- GUI 실행 시 sys.executable 사용.
- sample_app_send_text_gui.py 경로 절대경로화 및 존재 여부 체크, 에러 표시.
- 실행 경로/분기 로그 출력 강화.
"""

import csv
import pickle
import shlex
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QDialog, QHeaderView, QPushButton,
    QTableWidgetItem, QWidget, QMessageBox
)

from MiniCmdUtil import MiniCmdUtil
from UiCommandsystemdialog import UiCommandsystemdialog

# 이 파일 위치 기준 (…/Subsystems/cmdGui)
ROOTDIR = Path(__file__).resolve().parent  # 기존: Path(sys.argv[0]).resolve().parent

# --------------------------------------------------------------------------------
# -- CommandSystem 클래스
# --------------------------------------------------------------------------------
class CommandSystem(QDialog, UiCommandsystemdialog):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.move(800, 100)
        self.mcu = None

        # 더 이상 TelemetryListener는 사용하지 않음
        self.telemetry_listener = None

    # -------- 내부 유틸 --------
    def _launch_sample_app_text_gui(self, caller: str):
        """
        sample_app_send_text_gui.py 실행 (경로·실행자 안전화)
        """
        gui_path = (ROOTDIR / "sample_app_send_text_gui.py").resolve()
        if not gui_path.is_file():
            QMessageBox.critical(
                self, "Error",
                f"sample_app_send_text_gui.py not found:\n{gui_path}"
            )
            print(f"[ERROR] GUI script not found: {gui_path}")
            return

        try:
            print(f"[INFO] Launching SAMPLE_APP Text GUI ({caller}): {sys.executable} {gui_path}")
            subprocess.Popen([sys.executable, str(gui_path)])
            with open(ROOTDIR / "SentCommandLogs.txt", "a", encoding="utf-8") as logf:
                logf.write(f"[{datetime.now()}] GUI Opened for SAMPLE_APP Text Send ({caller})\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch GUI:\n{e}")
            print(f"[ERROR] Failed to launch GUI: {e}")

    # -------- Display Page 버튼 --------
    def process_button_generic(self, idx):
        """
        [Display Page] 버튼 클릭 시 호출됩니다.
        'Sample App' 계열이면 텍스트 GUI를 실행하고,
        아니면 기존 방식대로 파라미터 GUI/명령 GUI를 실행합니다.
        """
        if not cmd_page_is_valid[idx]:
            return

        raw_name = self.tbl_cmd_sys.item(idx, 0).text()
        app_name = (raw_name or "").strip()
        app_name_l = app_name.lower()
        print(f"[DEBUG] Display Page clicked: idx={idx}, name={app_name!r}")

        # --- Sample App 텍스트 GUI 분기 (라벨이 조금 달라도 허용) ---
        # 예: "Sample App", "Sample App (CPU1)", "Sample App Text Send", 등
        if ("sample app" in app_name_l) and (("text" in app_name_l) or ("send" in app_name_l) or ("sample app" == app_name_l)):
            self._launch_sample_app_text_gui("via Display Page")
            return

        # --- 기본 명령 GUI 로직 (기존) ---
        pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
        address = self.tbl_cmd_sys.item(idx, 2).text()
        launch_string = (
            f'{sys.executable} {ROOTDIR}/{cmdClass[idx]} '
            f'--title="{cmdPageDesc[idx]}" --pktid={pkt_id} '
            f'--file={cmdPageDefFile[idx]} --address="{address}" '
            f'--port={cmdPagePort[idx]} --endian={cmdPageEndian[idx]}'
        )
        print(f"[INFO] Launching command GUI: {launch_string}")
        cmd_args = shlex.split(launch_string)
        subprocess.Popen(cmd_args)

    @staticmethod
    def check_params(idx):
        """
        Quick Command에 필요한 파라미터 파일이 존재하는지 확인합니다.
        """
        pickle_file = f'{ROOTDIR}/ParameterFiles/{quick_param[idx]}'
        try:
            with open(pickle_file, 'rb') as pickle_obj:
                param_names = pickle.load(pickle_obj)[1]
            return len(param_names) > 0
        except IOError:
            return False

    # -------- Quick Command 버튼 --------
    def process_quick_button(self, idx):
        """
        Quick Button 클릭 시 호출됩니다.
        Sample App 텍스트라면 GUI를 실행하고,
        아니라면 파라미터 유무에 따라 MiniCmdUtil 또는 파라미터 GUI 실행.
        """
        if not (cmd_page_is_valid[idx] and quick_indices[idx] >= 0):
            return

        q_idx = quick_indices[idx]
        pkt_id = self.tbl_cmd_sys.item(idx, 1).text()
        address = self.tbl_cmd_sys.item(idx, 2).text()

        name = (subsys[q_idx] or "").strip().lower()
        quick_label = (quick_cmd[q_idx] or "").strip().lower()
        print(f"[DEBUG] Quick button clicked: idx={idx}, subsys={name!r}, quick_cmd={quick_label!r}")

        # Sample App Text GUI (유연한 조건)
        need_text_gui = (("sample app" in name) and (("text" in name) or (quick_label == "send text")))
        if need_text_gui:
            self._launch_sample_app_text_gui("via Quick Command")
            return

        # 파라미터 파일이 있으면 Parameter.py로 실행
        if self.check_params(q_idx):
            launch_string = (
                f'{sys.executable} {ROOTDIR}/Parameter.py '
                f'--title="{subsys[q_idx]}" '
                f'--descrip="{quick_cmd[q_idx]}" '
                f'--idx={idx} --host="{address}" '
                f'--port={quick_port[q_idx]} '
                f'--pktid={pkt_id} --endian={quick_endian[q_idx]} '
                f'--cmdcode={quick_code[q_idx]} --file={quick_param[q_idx]}'
            )
            print(f"[INFO] Launching parameter GUI: {launch_string}")
            cmd_args = shlex.split(launch_string)
            subprocess.Popen(cmd_args)
        else:
            # 바로 전송
            self.mcu = MiniCmdUtil(
                address, quick_port[q_idx],
                quick_endian[q_idx], pkt_id,
                quick_code[q_idx]
            )
            send_success = self.mcu.send_packet()
            print("Command sent successfully:", send_success)

    # -------- 텔레메트리 실행 --------
    def on_start_telemetry(self):
        """
        “Start Telemetry” 버튼 클릭 시 호출됩니다.
        기존 TelemetrySystem을 실행하는 로직을 수행합니다.
        """
        self.start_tlm_system(self.cb_ips.currentText())

    def start_tlm_system(self, selected_spacecraft):
        """
        TelemetrySystem을 실행합니다.
        """
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All':
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        args = shlex.split(
            f'{sys.executable} {ROOTDIR}/Subsystems/tlmGUI/TelemetrySystem.py {subscription}'
        )
        subprocess.Popen(args)
        self.log_output.append(f"<font color='blue'>[시스템] Telemetry System Started</font>")

    # -------- 기타 UI 핸들러(원본 유지) --------
    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System is already running.")
            return
        cmd = [sys.executable, '-u', f'{ROOTDIR}/Subsystems/cmdGui/CommandSystem.py']
        self.cmd_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        self.cmd_process_reader = CmdProcessReader(self.cmd_process)
        if on_stdout_callback:
            self.cmd_process_reader.line_received.connect(on_stdout_callback)
        self.cmd_process_reader.start()
        self.log_output.append(f"<font color='blue'>[시스템] Command System Started</font>")

    def on_cmd_header_changed(self, txt):
        self.gs_logic.set_cmd_offsets(txt)
        self.sb_cmd_pri.setEnabled(txt == "Custom")
        self.sb_cmd_sec.setEnabled(txt == "Custom")
        self.sb_cmd_pri.setValue(self.gs_logic.sb_cmd_offset_pri_value)
        self.sb_cmd_sec.setValue(self.gs_logic.sb_cmd_offset_sec_value)
        self.gs_logic.save_offsets()

    def on_cmd_offset_pri_changed(self, v):
        self.gs_logic.sb_cmd_offset_pri_value = v
        self.gs_logic.save_offsets()

    def on_cmd_offset_sec_changed(self, v):
        self.gs_logic.sb_cmd_offset_sec_value = v
        self.gs_logic.save_offsets()

    def on_tlm_header_changed(self, txt):
        self.gs_logic.set_tlm_offset(txt)
        self.sb_tlm_offset.setEnabled(txt == "Custom")
        self.sb_tlm_offset.setValue(self.gs_logic.sb_tlm_offset_value)
        self.gs_logic.save_offsets()

    def on_tlm_offset_changed(self, v):
        self.gs_logic.sb_tlm_offset_value = v
        self.gs_logic.save_offsets()

    def clear_cmd_log(self):
        self.log_output.clear()
        self.log_output.append(f"<font color='blue'>[시스템] 커맨드 로그가 초기화되었습니다.</font>")

    def show_error_message(self, msg):
        QMessageBox.warning(self, "Error", msg)

    def append_terminal_output(self, msg: str):
        color = "blue" if msg.startswith("[시스템]") else "red" if msg.startswith("[공격]") else "black"
        self.log_output.append(f"<font color='{color}'>{msg}</font>")

    def on_start_tlm(self):
        self.on_start_telemetry()

    def closeEvent(self, ev):
        if self.mcu:
            try:
                self.mcu.mm.close()
            except Exception:
                pass
        super().closeEvent(ev)


# Main
if __name__ == "__main__":
    cmd_def_file = "command-pages.txt"

    app = QApplication(sys.argv)
    command = CommandSystem()
    tbl = command.tbl_cmd_sys

    # CSV 및 동적 테이블 로드 로직 (command-pages.txt)
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

