#!/usr/bin/env python3
import sys
import os
import shlex
import subprocess
import signal
import pathlib
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout,
    QVBoxLayout, QGroupBox, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QDialog
)
from OpenGL.GL import *
from OpenGL.GLU import *

from modeling import EarthSatelliteView
from satellite_setting import SatelliteSettingsDialog

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
        self.sb_tlm_offset_value     = self.TLM_HDR_V1_OFFSET
        self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V1_OFFSET
        self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V1_OFFSET
        self.ip_addresses_list       = ['All']
        self.spacecraft_names        = ['All']
        self.routing_service         = None
        self.cmd_process             = None
        self.cmd_process_reader      = None

    def display_error_message(self, message: str):
        print("[ERROR]", message)
        if self.display_error_callback:
            self.display_error_callback(message)

    def get_selected_spacecraft_name(self, combo_box_text: str):
        idx = self.ip_addresses_list.index(combo_box_text)
        return self.spacecraft_names[idx]

    def start_tlm_system(self, selected_spacecraft: str):
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All':
            subscription += f'.{selected_spacecraft}.TelemetryPackets'
        args = shlex.split(
            f'python3 {self.ROOTDIR}/Subsystems/tlmGUI/TelemetrySystem.py {subscription}'
        )
        subprocess.Popen(args)

    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System is already running.")
            return
        cmd = ['python3', '-u', f'{self.ROOTDIR}/Subsystems/cmdGui/CommandSystem.py']
        self.cmd_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
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

    def set_tlm_offset(self, ver: str):
        self.sb_tlm_offset_value = (
            self.TLM_HDR_V1_OFFSET if ver == '1' else self.TLM_HDR_V2_OFFSET
        )

    def set_cmd_offsets(self, ver: str):
        if ver == '1':
            self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V1_OFFSET
            self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V1_OFFSET
        else:
            self.sb_cmd_offset_pri_value = self.CMD_HDR_PRI_V2_OFFSET
            self.sb_cmd_offset_sec_value = self.CMD_HDR_SEC_V2_OFFSET

    def save_offsets(self):
        with open('/tmp/OffsetData', 'wb') as f:
            f.write(bytes((
                self.sb_tlm_offset_value,
                self.sb_cmd_offset_pri_value,
                self.sb_cmd_offset_sec_value
            )))

    def update_ip_list(self, ip, name):
        self.ip_addresses_list.append(ip)
        self.spacecraft_names.append(name)

    def init_routing_service(self, routing_service):
        self.routing_service = routing_service
        self.routing_service.signal_update_ip_list.connect(self.update_ip_list)
        self.routing_service.start()

class NextGenGroundSystem(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("차세대 위성통신 보안 시뮬레이터 (New GUI)")
        self.resize(1200, 800)

        # persistent settings
        self.settings = QSettings("MyCompany", "SatelliteComSim")

        self.ROOTDIR  = pathlib.Path(__file__).parent.absolute()
        self.gs_logic = GroundSystemLogic(self.ROOTDIR,
                            display_error_callback=self.show_error_message)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)
        h_layout.setContentsMargins(5, 5, 5, 5)

        # Left: 3D view & satellite button
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.earth_view = EarthSatelliteView(
            model_path     = str(self.ROOTDIR / "earth.glb"),
            texture_path   = str(self.ROOTDIR / "textures" / "image_0.png"),
            bg_image_path  = str(self.ROOTDIR / "textures" / "background.jpg"),
            sat_model_path = str(self.ROOTDIR / "textures" / "satellite.glb"),
            parent         = self
        )
        left_layout.addWidget(self.earth_view, stretch=4)

        # load saved satellite parameters
        saved = self.settings.value("satellite/params", type=dict) or {}
        if saved:
            self.earth_view.updateSatelliteParameters(**saved)

        btn_sat = QPushButton("위성 설정")
        btn_sat.clicked.connect(self.openSatelliteSettings)
        left_layout.addWidget(btn_sat)

        h_layout.addWidget(left_panel, stretch=5)

        # Right: log output & controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
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

        self.sb_cmd_pri = QSpinBox()
        self.sb_cmd_pri.setRange(0, 64)
        self.sb_cmd_pri.setValue(self.gs_logic.sb_cmd_offset_pri_value)
        self.sb_cmd_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form_layout.addRow("CMD Offset PRI", self.sb_cmd_pri)

        self.sb_cmd_sec = QSpinBox()
        self.sb_cmd_sec.setRange(0, 64)
        self.sb_cmd_sec.setValue(self.gs_logic.sb_cmd_offset_sec_value)
        self.sb_cmd_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form_layout.addRow("CMD Offset SEC", self.sb_cmd_sec)

        control_layout.addLayout(form_layout)
        control_layout.addWidget(QLabel("IP 선택"))
        self.cb_ips = QComboBox()
        self.cb_ips.addItem("All")
        control_layout.addWidget(self.cb_ips)

        btn_tlm = QPushButton("Start Telemetry")
        btn_tlm.clicked.connect(self.on_start_tlm)
        btn_cmd = QPushButton("Start Command")
        btn_cmd.clicked.connect(self.on_start_cmd)
        control_layout.addWidget(btn_tlm)
        control_layout.addWidget(btn_cmd)

        btn_clear = QPushButton("커맨드 로그 초기화")
        btn_clear.clicked.connect(self.clear_cmd_log)
        control_layout.addWidget(btn_clear)

        control_layout.addWidget(QLabel("사이버 공격"))
        atk_layout = QHBoxLayout()
        for lbl in ["재밍", "스푸핑", "재전송"]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda _,m=lbl: self.append_terminal_output(f"[공격] {m} 실행"))
            atk_layout.addWidget(b)
        control_layout.addLayout(atk_layout)

        right_layout.addWidget(control_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

        self.init_routing_service()

    def openSatelliteSettings(self):
        dlg = SatelliteSettingsDialog(self)
        curr = self.earth_view.getCurrentParameters()
        dlg.cb_sat_type.setCurrentText(curr['sat_type'])
        dlg.ds_sat_size.setValue(curr['sat_size'])
        dlg.ds_sat_speed.setValue(curr['sat_speed'])
        dlg.ds_orbital_radius.setValue(curr['orbital_radius'])
        dlg.ds_inclination.setValue(curr['inclination'])
        dlg.ds_eccentricity.setValue(curr['eccentricity'])
        dlg.ds_frequency.setValue(curr['frequency'])
        dlg.ds_antenna_gain.setValue(curr['antenna_gain'])
        dlg.ds_transmit_power.setValue(curr['transmit_power'])

        if dlg.exec_() == QDialog.Accepted:
            params = dlg.getParameters()
            self.earth_view.updateSatelliteParameters(**params)
            self.settings.setValue("satellite/params", params)
            self.append_terminal_output(
                f"[시스템] 위성 파라미터 변경됨: 크기={params['sat_size']}, 속도={params['sat_speed']} 등..."
            )

    def clear_cmd_log(self):
        self.log_output.clear()
        self.append_terminal_output("[시스템] 커맨드 로그가 초기화되었습니다.")

    def show_error_message(self, msg):
        QMessageBox.warning(self, "Error", msg)

    def append_terminal_output(self, msg: str):
        color = "blue" if msg.startswith("[시스템]") else "red" if msg.startswith("[공격]") else "black"
        self.log_output.append(f"<font color='{color}'>{msg}</font>")

    def on_start_tlm(self):
        sc = self.gs_logic.get_selected_spacecraft_name(self.cb_ips.currentText())
        self.gs_logic.start_tlm_system(sc)
        self.append_terminal_output("[시스템] Telemetry System Started")

    def on_start_cmd(self):
        def handler(line): self.append_terminal_output(f"[CMD] {line}")
        self.gs_logic.start_cmd_system(on_stdout_callback=handler)
        self.append_terminal_output("[시스템] Command System Started")

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

    def init_routing_service(self):
        from RoutingService import RoutingService
        self.routing_service = RoutingService()
        self.routing_service.signal_update_ip_list.connect(self.on_ip_list_updated)
        self.routing_service.start()

    def on_ip_list_updated(self, ip, name):
        self.gs_logic.update_ip_list(ip, name)
        self.cb_ips.addItem(ip)

    def closeEvent(self, ev):
        self.gs_logic.stop_cmd_system()
        if self.gs_logic.routing_service:
            self.gs_logic.routing_service.stop()
        os.kill(0, signal.SIGKILL)
        super().closeEvent(ev)

def main():
    from _version import __version__, _version_string
    print(_version_string)
    app = QApplication(sys.argv)
    window = NextGenGroundSystem()
    window.show()
    window.raise_()
    window.gs_logic.save_offsets()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

