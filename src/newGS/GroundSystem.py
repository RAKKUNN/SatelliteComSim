#!/usr/bin/env python3
import sys
import os
import shlex
import subprocess
import signal
import pathlib
from math import cos, sin, pi
from io import BytesIO

import numpy as np

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout,
    QVBoxLayout, QGroupBox, QFormLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QSpinBox, QTextEdit, QSizePolicy, QDialog, QDialogButtonBox, QOpenGLWidget
)
from PyQt5.QtGui import QImage, QPixmap

from OpenGL.GL import *
from OpenGL.GLU import *

# 3D 관련 코드는 분리된 모듈(3D_modeling.py)에서 임포트합니다.
from modeling import EarthSatelliteView
# 위성 파라미터 설정 다이얼로그는 satellite_setting.py에 정의된 클래스를 사용합니다.
from satellite_setting import SatelliteSettingsDialog


# 1) CmdProcessReader: subprocess의 stdout을 읽어오는 스레드
class CmdProcessReader(QThread):
    line_received = pyqtSignal(str)

    def __init__(self, process, parent=None):
        super().__init__(parent)
        self.process = process
        self._running = True

    def run(self):
        while self._running:
            line = self.process.stdout.readline()
            if not line:
                break
            self.line_received.emit(line.rstrip('\n'))

    def stop(self):
        self._running = False


# 2) GroundSystemLogic: 기존 GS 핵심 기능 (텔레메트리, 명령, FDL, 라우팅 등)
class GroundSystemLogic:
    TLM_HDR_V1_OFFSET = 4
    TLM_HDR_V2_OFFSET = 4
    CMD_HDR_PRI_V1_OFFSET = 0
    CMD_HDR_SEC_V1_OFFSET = 0
    CMD_HDR_PRI_V2_OFFSET = 4
    CMD_HDR_SEC_V2_OFFSET = 4

    def __init__(self, rootdir, display_error_callback=None):
        self.ROOTDIR = rootdir
        self.display_error_callback = display_error_callback
        self.sb_tlm_offset_value = self.TLM_HDR_V1_OFFSET
        self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V1_OFFSET
        self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V1_OFFSET
        self.ip_addresses_list = ['All']
        self.spacecraft_names = ['All']
        self.routing_service = None
        self.cmd_process = None
        self.cmd_process_reader = None

    def display_error_message(self, message: str):
        print("[ERROR]", message)
        if self.display_error_callback:
            self.display_error_callback(message)

    def get_selected_spacecraft_name(self, combo_box_text: str):
        address = combo_box_text.strip()
        idx = self.ip_addresses_list.index(address)
        return self.spacecraft_names[idx].strip()

    def start_tlm_system(self, selected_spacecraft: str):
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All':
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        system_call = f'python3 {self.ROOTDIR}/Subsystems/tlmGUI/TelemetrySystem.py {subscription}'
        args = shlex.split(system_call)
        subprocess.Popen(args)

    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System is already running.")
            return
        cmd = ['python3', '-u', f'{self.ROOTDIR}/Subsystems/cmdGui/CommandSystem.py']
        self.cmd_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.cmd_process_reader = CmdProcessReader(self.cmd_process)
        if on_stdout_callback:
            self.cmd_process_reader.line_received.connect(on_stdout_callback)
        self.cmd_process_reader.start()

    def stop_cmd_system(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.cmd_process.terminate()
        if self.cmd_process_reader:
            self.cmd_process_reader.stop()
            self.cmd_process_reader.quit()
            self.cmd_process_reader.wait()

    def start_fdl_system(self, selected_spacecraft: str):
        if selected_spacecraft == 'All':
            self.display_error_message('Cannot open FDL manager.\nNo spacecraft selected.')
        else:
            subscription = f'--sub=GroundSystem.{selected_spacecraft}'
            subprocess.Popen(['python3', f'{self.ROOTDIR}/Subsystems/fdlGui/FdlSystem.py', subscription])

    def set_tlm_offset(self, ver: str):
        if ver == "Custom":
            pass
        else:
            if ver == "1":
                self.sb_tlm_offset_value = self.TLM_HDR_V1_OFFSET
            elif ver == "2":
                self.sb_tlm_offset_value = self.TLM_HDR_V2_OFFSET

    def set_cmd_offsets(self, ver: str):
        if ver == "Custom":
            pass
        else:
            if ver == "1":
                self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V1_OFFSET
                self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V1_OFFSET
            elif ver == "2":
                self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V2_OFFSET
                self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V2_OFFSET

    def save_offsets(self):
        offsets = bytes((
            self.sb_tlm_offset_value,
            self.sb_cmd_offset_pri_value,
            self.sb_cmd_offset_sec_value
        ))
        with open("/tmp/OffsetData", "wb") as f:
            f.write(offsets)

    def update_ip_list(self, ip, name):
        self.ip_addresses_list.append(ip)
        self.spacecraft_names.append(name)

    def init_routing_service(self, routing_service):
        self.routing_service = routing_service
        self.routing_service.signal_update_ip_list.connect(self.update_ip_list)
        self.routing_service.start()


# 3) NextGenGroundSystem: GS 전체 GUI
class NextGenGroundSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("차세대 위성통신 보안 시뮬레이터 (New GUI)")
        self.resize(1200, 800)
        self.ROOTDIR = pathlib.Path(__file__).parent.absolute()
        self.gs_logic = GroundSystemLogic(self.ROOTDIR, display_error_callback=self.show_error_message)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)
        h_layout.setContentsMargins(5, 5, 5, 5)
        h_layout.setSpacing(10)

        # Left Panel: 3D 모델 영역 및 하단 설정 버튼들
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setSpacing(10)
        self.earth_view = EarthSatelliteView()
        self.earth_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_panel_layout.addWidget(self.earth_view, stretch=4)
        button_layout = QHBoxLayout()
        btn_base_station = QPushButton("기지국 설정")
        btn_satellite = QPushButton("위성 설정")
        btn_comm = QPushButton("통신 설정")
        button_layout.addWidget(btn_base_station)
        button_layout.addWidget(btn_satellite)
        button_layout.addWidget(btn_comm)
        left_panel_layout.addLayout(button_layout, stretch=1)
        h_layout.addWidget(left_panel, stretch=5)

        # Right Panel: 로그 영역 및 제어/공격 패널
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.log_output, stretch=3)

        control_box = QGroupBox("제어 / 공격 시뮬레이션")
        control_layout = QVBoxLayout(control_box)
        form_layout = QFormLayout()
        self.cb_tlm_header = QComboBox()
        self.cb_tlm_header.addItems(["1", "2", "Custom"])
        self.cb_tlm_header.currentTextChanged.connect(self.on_tlm_header_changed)
        form_layout.addRow("TLM Header Ver", self.cb_tlm_header)
        self.sb_tlm_offset = QSpinBox()
        self.sb_tlm_offset.setRange(0, 64)
        self.sb_tlm_offset.setValue(self.gs_logic.sb_tlm_offset_value)
        self.sb_tlm_offset.valueChanged.connect(self.on_tlm_offset_changed)
        form_layout.addRow("TLM Offset", self.sb_tlm_offset)
        self.cb_cmd_header = QComboBox()
        self.cb_cmd_header.addItems(["1", "2", "Custom"])
        self.cb_cmd_header.currentTextChanged.connect(self.on_cmd_header_changed)
        form_layout.addRow("CMD Header Ver", self.cb_cmd_header)
        self.sb_cmd_offset_pri = QSpinBox()
        self.sb_cmd_offset_pri.setRange(0, 64)
        self.sb_cmd_offset_pri.setValue(self.gs_logic.sb_cmd_offset_pri_value)
        self.sb_cmd_offset_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form_layout.addRow("CMD Offset PRI", self.sb_cmd_offset_pri)
        self.sb_cmd_offset_sec = QSpinBox()
        self.sb_cmd_offset_sec.setRange(0, 64)
        self.sb_cmd_offset_sec.setValue(self.gs_logic.sb_cmd_offset_sec_value)
        self.sb_cmd_offset_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form_layout.addRow("CMD Offset SEC", self.sb_cmd_offset_sec)
        control_layout.addLayout(form_layout)
        control_layout.addWidget(QLabel("IP 선택"))
        self.cb_ip_addresses = QComboBox()
        self.cb_ip_addresses.addItem("All")
        control_layout.addWidget(self.cb_ip_addresses)
        btn_tlm = QPushButton("Start Telemetry")
        btn_tlm.clicked.connect(self.on_start_tlm)
        control_layout.addWidget(btn_tlm)
        btn_cmd = QPushButton("Start Command")
        btn_cmd.clicked.connect(self.on_start_cmd)
        control_layout.addWidget(btn_cmd)
        btn_fdl = QPushButton("Start FDL")
        btn_fdl.clicked.connect(self.on_start_fdl)
        control_layout.addWidget(btn_fdl)
        control_layout.addWidget(QLabel("사이버 공격"))
        attack_layout = QHBoxLayout()
        btn_jamming = QPushButton("재밍")
        btn_spoofing = QPushButton("스푸핑")
        btn_key_theft = QPushButton("재전송")
        attack_layout.addWidget(btn_jamming)
        attack_layout.addWidget(btn_spoofing)
        attack_layout.addWidget(btn_key_theft)
        control_layout.addLayout(attack_layout)
        btn_jamming.clicked.connect(lambda: self.append_terminal_output("[공격] 재밍 실행"))
        btn_spoofing.clicked.connect(lambda: self.append_terminal_output("[공격] 스푸핑 실행"))
        btn_key_theft.clicked.connect(lambda: self.append_terminal_output("[공격] 재전송 실행"))
        right_layout.addWidget(control_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

        btn_satellite.clicked.connect(self.openSatelliteSettings)
        self.init_routing_service()

    def openSatelliteSettings(self):
        dialog = SatelliteSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            params = dialog.getParameters()
            self.earth_view.updateSatelliteParameters(
                params["sat_type"],
                params["sat_size"],
                params["sat_speed"],
                params["orbital_radius"],
                params["inclination"],
                params["eccentricity"],
                params["frequency"],
                params["antenna_gain"],
                params["transmit_power"]
            )
            self.append_terminal_output(
                f"[시스템] 위성 파라미터 적용: 종류={params['sat_type']}, 크기={params['sat_size']}, 속도={params['sat_speed']}, 궤도높이={params['orbital_radius']}, 경사각={params['inclination']}, 이심률={params['eccentricity']}, 주파수={params['frequency']}, 안테나이득={params['antenna_gain']}, 송신전력={params['transmit_power']}"
            )

    def init_routing_service(self):
        from RoutingService import RoutingService
        self.routing_service = RoutingService()
        self.routing_service.signal_update_ip_list.connect(self.on_ip_list_updated)
        self.routing_service.start()

    def on_ip_list_updated(self, ip, name):
        self.gs_logic.update_ip_list(ip, name)
        self.cb_ip_addresses.addItem(ip)

    def closeEvent(self, event):
        self.gs_logic.stop_cmd_system()
        if self.gs_logic.routing_service:
            self.gs_logic.routing_service.stop()
            print("Stopped routing service")
        os.kill(0, signal.SIGKILL)
        super().closeEvent(event)

    def show_error_message(self, message):
        QMessageBox.warning(self, "Error", message)

    def append_terminal_output(self, message: str):
        if message.startswith("[시스템]"):
            color = "blue"
        elif message.startswith("[CMD]"):
            color = "black"
        elif message.startswith("[공격]"):
            color = "red"
        else:
            color = "black"
        formatted_message = f"<font color='{color}'>{message}</font>"
        self.log_output.append(formatted_message)

    def on_start_tlm(self):
        selected_ip = self.cb_ip_addresses.currentText()
        sc_name = self.gs_logic.get_selected_spacecraft_name(selected_ip)
        self.gs_logic.start_tlm_system(sc_name)
        self.append_terminal_output("[시스템] Telemetry System Started")

    def on_start_cmd(self):
        def handle_cmd_stdout(line: str):
            self.append_terminal_output(f"[CMD] {line}")
        self.gs_logic.start_cmd_system(on_stdout_callback=handle_cmd_stdout)
        self.append_terminal_output("[시스템] Command System Started")

    def on_start_fdl(self):
        selected_ip = self.cb_ip_addresses.currentText()
        sc_name = self.gs_logic.get_selected_spacecraft_name(selected_ip)
        self.gs_logic.start_fdl_system(sc_name)
        self.append_terminal_output("[시스템] FDL System Started")

    def on_tlm_header_changed(self, text):
        self.gs_logic.set_tlm_offset(text)
        if text == "Custom":
            self.sb_tlm_offset.setEnabled(True)
        else:
            self.sb_tlm_offset.setEnabled(False)
            self.sb_tlm_offset.setValue(self.gs_logic.sb_tlm_offset_value)
        self.gs_logic.save_offsets()

    def on_tlm_offset_changed(self, val):
        self.gs_logic.sb_tlm_offset_value = val
        self.gs_logic.save_offsets()

    def on_cmd_header_changed(self, text):
        self.gs_logic.set_cmd_offsets(text)
        if text == "Custom":
            self.sb_cmd_offset_pri.setEnabled(True)
            self.sb_cmd_offset_sec.setEnabled(True)
        else:
            self.sb_cmd_offset_pri.setEnabled(False)
            self.sb_cmd_offset_sec.setEnabled(False)
            self.sb_cmd_offset_pri.setValue(self.gs_logic.sb_cmd_offset_pri_value)
            self.sb_cmd_offset_sec.setValue(self.gs_logic.sb_cmd_offset_sec_value)
        self.gs_logic.save_offsets()

    def on_cmd_offset_pri_changed(self, val):
        self.gs_logic.sb_cmd_offset_pri_value = val
        self.gs_logic.save_offsets()

    def on_cmd_offset_sec_changed(self, val):
        self.gs_logic.sb_cmd_offset_sec_value = val
        self.gs_logic.save_offsets()


# 5) 메인 함수
def main():
    from _version import __version__ as _version
    from _version import _version_string
    print(_version_string)
    app = QApplication(sys.argv)
    window = NextGenGroundSystem()
    window.show()
    window.raise_()
    window.gs_logic.save_offsets()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

