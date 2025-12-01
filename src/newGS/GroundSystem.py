#!/usr/bin/env python3
import sys
import os
import shlex
import subprocess
import signal
import pathlib  # pathlib 임포트 유지
import json
import socket
from datetime import datetime, timezone
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QHBoxLayout,
    QVBoxLayout, QGroupBox, QFormLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QDialog
)

from modeling import EarthSatelliteView
from satellite_setting import SatelliteSettingsDialog
from base_station_setting import BaseStationSettingsDialog  # 기지국 설정 다이얼로그
from comm_setting import CommSettingsDialog                  # ★ 추가


# ──────────────────────────────────────────────────────────────────────────────
# CmdProcessReader: subprocess stdout을 QThread로 읽어 와 시그널로 전달
# ──────────────────────────────────────────────────────────────────────────────
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
            self.line_received.emit(line.rstrip("\n"))

    def stop(self):
        self._running = False


# ──────────────────────────────────────────────────────────────────────────────
# GroundSystemLogic: GS 내부 로직
# ──────────────────────────────────────────────────────────────────────────────
class GroundSystemLogic:
    TLM_HDR_V1_OFFSET = 4
    TLM_HDR_V2_OFFSET = 4     # TODO: 실제 V2 오프셋 값 확인/수정
    CMD_HDR_PRI_V1_OFFSET = 0
    CMD_HDR_SEC_V1_OFFSET = 0
    CMD_HDR_PRI_V2_OFFSET = 4 # TODO
    CMD_HDR_SEC_V2_OFFSET = 4 # TODO

    def __init__(self, rootdir, display_error_callback=None):
        self.ROOTDIR = rootdir  # pathlib.Path
        self.display_error_callback = display_error_callback

        self.ip_addresses_list = ['All']
        self.spacecraft_names = ['All']

        self.routing_service = None
        self.cmd_process = None
        self.cmd_process_reader = None

    def display_error_message(self, message: str):
        print(f"[GS_LOGIC_ERROR] {message}")
        if self.display_error_callback:
            self.display_error_callback(message)

    def get_selected_spacecraft_name(self, combo_box_text: str):
        try:
            if combo_box_text in self.ip_addresses_list:
                idx = self.ip_addresses_list.index(combo_box_text)
                if idx < len(self.spacecraft_names):
                    return self.spacecraft_names[idx]
            return combo_box_text
        except ValueError:
            return "All"

    def start_tlm_system(self, selected_spacecraft: str):
        subscription = '--sub=GroundSystem'
        if selected_spacecraft != 'All' and selected_spacecraft in self.spacecraft_names:
            subscription += f'.{selected_spacecraft}.TelemetryPackets'

        tlm_system_path = self.ROOTDIR / "Subsystems" / "tlmGUI" / "TelemetrySystem.py"
        if not tlm_system_path.is_file():
            self.display_error_message(f"TelemetrySystem.py를 찾을 수 없습니다: {tlm_system_path}")
            return
        args = shlex.split(f'python3 {str(tlm_system_path)} {subscription}')
        try:
            subprocess.Popen(args)
        except Exception as e:
            self.display_error_message(f"Telemetry System 시작 실패: {e}")

    def start_cmd_system(self, on_stdout_callback=None):
        if self.cmd_process and self.cmd_process.poll() is None:
            self.display_error_message("Command System이 이미 실행 중입니다.")
            return

        cmd_system_path = self.ROOTDIR / "Subsystems" / "cmdGui" / "CommandSystem.py"
        if not cmd_system_path.is_file():
            self.display_error_message(f"CommandSystem.py를 찾을 수 없습니다: {cmd_system_path}")
            return

        cmd = ['python3', '-u', str(cmd_system_path)]
        try:
            self.cmd_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            self.cmd_process_reader = CmdProcessReader(self.cmd_process)
            if on_stdout_callback:
                self.cmd_process_reader.line_received.connect(on_stdout_callback)
            self.cmd_process_reader.start()
        except Exception as e:
            self.display_error_message(f"Command System 시작 실패: {e}")

    def stop_cmd_system(self):
        if self.cmd_process and self.cmd_process.poll() is None:
            try:
                self.cmd_process.terminate()
            except Exception as e:
                print(f"[ERROR] Terminating cmd_process: {e}")
        if self.cmd_process_reader:
            try:
                self.cmd_process_reader.stop()
                self.cmd_process_reader.quit()
                self.cmd_process_reader.wait(1000)  # 1초 타임아웃
            except Exception as e:
                print(f"[ERROR] Stopping cmd_process_reader: {e}")

    def update_ip_list(self, ip, name):
        is_new_ip = True
        for i, existing_ip in enumerate(self.ip_addresses_list):
            if existing_ip == ip:
                if i < len(self.spacecraft_names) and self.spacecraft_names[i] != name:
                    self.spacecraft_names[i] = name
                is_new_ip = False
                break
        if is_new_ip:
            self.ip_addresses_list.append(ip)
            self.spacecraft_names.append(name)

    def init_routing_service(self, routing_service=None):
        try:
            from RoutingService import RoutingService  # 동적 임포트
            self.routing_service = routing_service or RoutingService()
            self.routing_service.signal_update_ip_list.connect(self.update_ip_list)
            self.routing_service.start()
            print("[SYSTEM] RoutingService started.")
        except ImportError:
            self.display_error_message("RoutingService.py를 찾을 수 없습니다. IP 목록이 동적으로 업데이트되지 않습니다.")
        except Exception as e:
            self.display_error_message(f"RoutingService 초기화 중 오류: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# NextGenGroundSystem: 메인 윈도우
# ──────────────────────────────────────────────────────────────────────────────
class NextGenGroundSystem(QMainWindow):
    DEFAULT_TLM_HDR_VER = "1"
    DEFAULT_CMD_HDR_VER = "1"

    DEFAULT_TLM_OFFSET = GroundSystemLogic.TLM_HDR_V1_OFFSET
    DEFAULT_CMD_OFFSET_PRI = GroundSystemLogic.CMD_HDR_PRI_V1_OFFSET
    DEFAULT_CMD_OFFSET_SEC = GroundSystemLogic.CMD_HDR_SEC_V1_OFFSET

    def __init__(self):
        super().__init__()
        self.setWindowTitle("차세대 위성통신 보안 시뮬레이터 (GroundSystem)")
        self.resize(1250, 850)

        QApplication.setOrganizationName("MySatComProject")
        QApplication.setApplicationName("GroundSystemGUI")
        self.settings = QSettings()

        self.ROOTDIR = pathlib.Path(__file__).resolve().parent
        self.gs_logic = GroundSystemLogic(self.ROOTDIR, self.show_error_message_box)
        self.attack_file_path = self.ROOTDIR / "attack_mode.txt"

        self.test2_process = None  # ★ test2 프로세스 핸들

        self._init_ui()
        self._load_settings()

        self.gs_logic.init_routing_service()  # RoutingService 시작

        self._initialize_attack_file()
        self._update_attack_ui_from_file()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        h_layout = QHBoxLayout(main_widget)

        # --- Left Panel (3D View and Settings Buttons) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        earth_model_path = self.ROOTDIR / "textures" / "earth.glb"
        earth_texture_path = self.ROOTDIR / "textures" / "image_0.png"
        bg_image_path = self.ROOTDIR / "textures" / "background.jpg"
        sat_model_path = self.ROOTDIR / "textures" / "satellite.glb"

        self.earth_view = EarthSatelliteView(
            model_path=str(earth_model_path), texture_path=str(earth_texture_path),
            bg_image_path=str(bg_image_path), sat_model_path=str(sat_model_path), parent=self
        )
        left_layout.addWidget(self.earth_view, stretch=4)

        button_layout = QHBoxLayout()
        buttons_to_add = [
            ("기지국 설정", self.openBaseStationSettings),
            ("위성 설정", self.openSatelliteSettings),
            ("통신 설정", self.openCommSettings)
        ]
        for name, callback in buttons_to_add:
            b = QPushButton(name)
            b.clicked.connect(callback)
            button_layout.addWidget(b)
        left_layout.addLayout(button_layout)
        h_layout.addWidget(left_panel, stretch=5)

        # --- Right Panel (Log Output and Control Box) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        right_layout.addWidget(self.log_output, stretch=3)

        control_box = QGroupBox("제어 / 공격 시뮬레이션")
        control_layout = QVBoxLayout(control_box)
        form_layout = QFormLayout()

        # TLM Header
        self.cb_tlm_header = QComboBox()
        self.cb_tlm_header.addItems(["1", "2", "Custom"])
        self.cb_tlm_header.currentTextChanged.connect(self.on_tlm_header_changed)
        form_layout.addRow("TLM Header Ver:", self.cb_tlm_header)

        self.sb_tlm_offset = QSpinBox()
        self.sb_tlm_offset.setRange(0, 64)
        self.sb_tlm_offset.valueChanged.connect(self.on_tlm_offset_changed)
        form_layout.addRow("TLM Offset:", self.sb_tlm_offset)

        # CMD Header
        self.cb_cmd_header = QComboBox()
        self.cb_cmd_header.addItems(["1", "2", "Custom"])
        self.cb_cmd_header.currentTextChanged.connect(self.on_cmd_header_changed)
        form_layout.addRow("CMD Header Ver:", self.cb_cmd_header)

        self.sb_cmd_pri = QSpinBox()
        self.sb_cmd_pri.setRange(0, 64)
        self.sb_cmd_pri.valueChanged.connect(self.on_cmd_offset_pri_changed)
        form_layout.addRow("CMD Offset PRI:", self.sb_cmd_pri)

        self.sb_cmd_sec = QSpinBox()
        self.sb_cmd_sec.setRange(0, 64)
        self.sb_cmd_sec.valueChanged.connect(self.on_cmd_offset_sec_changed)
        form_layout.addRow("CMD Offset SEC:", self.sb_cmd_sec)

        control_layout.addLayout(form_layout)

        control_layout.addWidget(QLabel("대상 IP 선택:"))
        self.cb_ips = QComboBox()
        self.cb_ips.addItem("All")
        if len(self.gs_logic.ip_addresses_list) > 1:
            for i, ip_addr in enumerate(self.gs_logic.ip_addresses_list):
                if ip_addr == "All":
                    continue
                name = self.gs_logic.spacecraft_names[i] if i < len(self.gs_logic.spacecraft_names) else ip_addr
                self.cb_ips.addItem(f"{name} ({ip_addr})", ip_addr)

        control_layout.addWidget(self.cb_ips)

        sys_ctrl_btn_layout = QHBoxLayout()
        for label, handler in [("Start Telemetry", self.on_start_tlm), ("Start Command", self.on_start_cmd), ("로그 초기화", self.clear_cmd_log)]:
            b = QPushButton(label)
            b.clicked.connect(handler)
            sys_ctrl_btn_layout.addWidget(b)
        control_layout.addLayout(sys_ctrl_btn_layout)

        control_layout.addWidget(QLabel("공격 유형 선택:"))
        self.attack_combo = QComboBox()
        self.attack_modes_kor_to_eng = {"없음": "none", "재밍": "jamming", "변조": "modify", "드랍": "drop", "노이즈": "noise"}
        self.attack_combo.addItems(self.attack_modes_kor_to_eng.keys())
        self.attack_combo.currentTextChanged.connect(self._update_attack_button_state_on_combo_change)
        control_layout.addWidget(self.attack_combo)

        self.attack_button = QPushButton("공격 시작")
        self.attack_button.setCheckable(True)
        self.attack_button.clicked.connect(self.toggle_attack_mode)
        control_layout.addWidget(self.attack_button)

        control_layout.addStretch()
        right_layout.addWidget(control_box, stretch=2)
        h_layout.addWidget(right_panel, stretch=3)

    def _initialize_attack_file(self):
        if not self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "w", encoding="utf-8") as f:
                    f.write("none")
                self.append_terminal_output(f"[시스템] '{self.attack_file_path}' 생성 및 'none'으로 초기화.")
            except Exception as e:
                self.append_terminal_output(f"[오류] attack_mode.txt 생성 실패: {e}")

    def _update_attack_ui_from_file(self):
        """ attack_mode.txt 내용으로 UI 상태 반영 """
        current_mode_eng = "none"
        if self.attack_file_path.exists():
            try:
                with open(self.attack_file_path, "r", encoding="utf-8") as f:
                    current_mode_eng = f.read().strip().lower()
            except Exception as e:
                self.append_terminal_output(f"[오류] attack_mode.txt 읽기 실패: {e}")

        mode_eng_to_kor = {v: k for k, v in self.attack_modes_kor_to_eng.items()}
        current_mode_kor = mode_eng_to_kor.get(current_mode_eng, "없음")

        self.attack_combo.setCurrentText(current_mode_kor)
        is_attacking = (current_mode_eng != "none")
        self.attack_button.setChecked(is_attacking)
        self.attack_button.setText("공격 중지" if is_attacking else "공격 시작")
        self.attack_combo.setEnabled(not is_attacking)
        self.attack_button.setEnabled(current_mode_kor != "없음" or is_attacking)

    def _load_settings(self):
        self.append_terminal_output("[시스템] 저장된 설정 로드 시도...")
        default_sat_params = getattr(self.earth_view, 'DEFAULT_PARAMS', {
            "sat_type": "소형 위성", "sat_size": 10.0, "sat_speed": 0.05,
            "orbital_radius": 300.0, "inclination": 45.0, "eccentricity": 0.0,
            "frequency": 2.4, "antenna_gain": 10.0, "transmit_power": 0.0
        })
        sat_params = self.settings.value("satellite/params", defaultValue=default_sat_params, type=dict)
        if sat_params:
            self.earth_view.updateSatelliteParameters(**sat_params)

        default_gs_params = {
            "gs_name": "Default GS", "gs_latitude": 36.350413, "gs_longitude": 127.384548,
            "gs_altitude": 50.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0
        }
        gs_params = self.settings.value("basestation/params", defaultValue=default_gs_params, type=dict)
        if gs_params and hasattr(self.earth_view, 'updateBaseStationMarker'):
            self.earth_view.updateBaseStationMarker(gs_params['gs_latitude'], gs_params['gs_longitude'], gs_params['gs_name'])

        self.cb_tlm_header.setCurrentText(self.settings.value("offsets/tlm_ver", self.DEFAULT_TLM_HDR_VER, type=str))
        self.sb_tlm_offset.setValue(self.settings.value("offsets/tlm_offset", self.DEFAULT_TLM_OFFSET, type=int))
        self.cb_cmd_header.setCurrentText(self.settings.value("offsets/cmd_ver", self.DEFAULT_CMD_HDR_VER, type=str))
        self.sb_cmd_pri.setValue(self.settings.value("offsets/cmd_pri", self.DEFAULT_CMD_OFFSET_PRI, type=int))
        self.sb_cmd_sec.setValue(self.settings.value("offsets/cmd_sec", self.DEFAULT_CMD_OFFSET_SEC, type=int))
        self.on_tlm_header_changed(self.cb_tlm_header.currentText())
        self.on_cmd_header_changed(self.cb_cmd_header.currentText())
        self.append_terminal_output("[시스템] 설정 로드 완료.")

    def _save_settings(self):
        self.settings.setValue("offsets/tlm_ver", self.cb_tlm_header.currentText())
        self.settings.setValue("offsets/tlm_offset", self.sb_tlm_offset.value())
        self.settings.setValue("offsets/cmd_ver", self.cb_cmd_header.currentText())
        self.settings.setValue("offsets/cmd_pri", self.sb_cmd_pri.value())
        self.settings.setValue("offsets/cmd_sec", self.sb_cmd_sec.value())
        self.append_terminal_output("[시스템] 현재 설정 저장됨.")

    def _update_attack_button_state_on_combo_change(self, selected_text_kor):
        if not self.attack_button.isChecked():
            self.attack_button.setEnabled(selected_text_kor != "없음")

    def toggle_attack_mode(self):
        is_checked_for_attack_start = self.attack_button.isChecked()
        selected_kor = self.attack_combo.currentText()

        if is_checked_for_attack_start and selected_kor == "없음":
            self.append_terminal_output("[공격] '없음'은 공격 유형이 아닙니다. 다른 유형을 선택 후 시작하세요.")
            self.attack_button.setChecked(False)
            return

        selected_mode_eng = self.attack_modes_kor_to_eng.get(selected_kor, "none") if is_checked_for_attack_start else "none"

        try:
            with open(self.attack_file_path, "w", encoding="utf-8") as f:
                f.write(selected_mode_eng)
            self.append_terminal_output(f"[공격] attack_mode.txt에 '{selected_mode_eng}' 모드 저장됨.")
        except Exception as e:
            self.append_terminal_output(f"[공격] attack_mode.txt 저장 실패: {e}")
            self.attack_button.setChecked(not is_checked_for_attack_start)
            return

        self.attack_button.setText("공격 중지" if is_checked_for_attack_start else "공격 시작")
        self.attack_combo.setEnabled(not is_checked_for_attack_start)
        log_msg = f"[공격] {selected_kor} ({selected_mode_eng}) 모드 적용됨." if selected_mode_eng != "none" \
            else "[공격] 모든 공격 중지됨 (none 모드)."
        self.append_terminal_output(log_msg)

    def openBaseStationSettings(self):
        dlg = BaseStationSettingsDialog(self)
        default_params = {"gs_name": "Default GS", "gs_latitude": 37.5665, "gs_longitude": 126.9780,
                          "gs_altitude": 30.0, "min_elevation": 5.0, "gs_antenna_gain": 35.0}
        params = self.settings.value("basestation/params", defaultValue=default_params, type=dict)
        dlg.setParameters(params)

        if dlg.exec_() == QDialog.Accepted:
            new_params = dlg.getParameters()
            self.settings.setValue("basestation/params", new_params)
            self.append_terminal_output(f"[시스템] 기지국 '{new_params['gs_name']}' 파라미터 저장됨.")
            if hasattr(self.earth_view, 'updateBaseStationMarker'):
                # ★ 오타 수정: gs_latlatitude -> gs_latitude
                self.earth_view.updateBaseStationMarker(new_params['gs_latitude'], new_params['gs_longitude'], new_params['gs_name'])

    def openSatelliteSettings(self):
        dlg = SatelliteSettingsDialog(self)
        default_params = getattr(self.earth_view, 'DEFAULT_PARAMS', {
            "sat_type": "소형 위성", "sat_size": 10.0, "sat_speed": 0.05,
            "orbital_radius": 300.0, "inclination": 45.0, "eccentricity": 0.0,
            "frequency": 2.4, "antenna_gain": 10.0, "transmit_power": 0.0
        })
        params = self.settings.value("satellite/params", defaultValue=default_params, type=dict)

        if hasattr(dlg, 'setParameters'):
            dlg.setParameters(params)
        else:
            dlg.cb_sat_type.setCurrentText(params.get('sat_type', default_params['sat_type']))
            dlg.ds_sat_size.setValue(params.get('sat_size', default_params['sat_size']))
            dlg.ds_sat_speed.setValue(params.get('sat_speed', default_params['sat_speed']))
            dlg.ds_orbital_radius.setValue(params.get('orbital_radius', default_params['orbital_radius']))
            dlg.ds_inclination.setValue(params.get('inclination', default_params['inclination']))
            dlg.ds_eccentricity.setValue(params.get('eccentricity', default_params['eccentricity']))
            dlg.ds_frequency.setValue(params.get('frequency', default_params['frequency']))
            dlg.ds_antenna_gain.setValue(params.get('antenna_gain', default_params['antenna_gain']))
            dlg.ds_transmit_power.setValue(params.get('transmit_power', default_params['transmit_power']))

        if dlg.exec_() == QDialog.Accepted:
            new_sat_params = dlg.getParameters()
            self.earth_view.updateSatelliteParameters(**new_sat_params)
            self.settings.setValue("satellite/params", new_sat_params)
            self.append_terminal_output(f"[시스템] 위성 '{new_sat_params['sat_type']}' 파라미터 저장됨.")

    # ★ 통신 설정: 다이얼로그 열기 → 저장 → test2 자동 실행/런타임 업데이트
    def openCommSettings(self):
        default_comm = {
            "listen_ip":"0.0.0.0","listen_port":8600,
            "dst_ip":"127.0.0.1","dst_port":1234,
            "mtu":1472,"ctrl_bind_ip":"127.0.0.1","ctrl_port":9696,
            "base_delay_ms":0.0,"jitter_ms":0.0,"ber":0.0,"seed":0xBEEF,
            "mode":"payload_only",
            "tlm08a9_len_off":12,"tlm08a9_text_off":14,"tlm08a9_text_max":128
        }
        comm_params = self.settings.value("comm/params", defaultValue=default_comm, type=dict)

        dlg = CommSettingsDialog(self, defaults=comm_params)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_params = dlg.get()
        self.settings.setValue("comm/params", new_params)

        # JSON 설정 파일로 저장 (test2가 자동 로드)
        cfg_path = self.ROOTDIR / "test2_config.json"
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(new_params, f, ensure_ascii=False, indent=2)
            self.append_terminal_output(f"[시스템] test2 설정 저장: {cfg_path.name}")
        except Exception as e:
            self.append_terminal_output(f"[오류] test2 설정 저장 실패: {e}")
            return

        # test2 실행 여부에 따라 동작
        if not self._is_test2_running():
            #self._start_test2(cfg_path)
            self.append_terminal_output("[시스템] 통신 설정 완료.")
        else:
            self._update_test2_runtime(new_params)

    def clear_cmd_log(self):
        self.log_output.clear()
        self.append_terminal_output("[시스템] 로그가 초기화되었습니다.")

    def show_error_message_box(self, msg):  # GroundSystemLogic 콜백용
        QMessageBox.critical(self, "오류 발생", msg)

    def append_terminal_output(self, msg: str):
        prefix_color_map = {"[시스템]": "blue", "[공격]": "red", "[CMD]": "green",
                            "[INFO]": "gray", "[WARN]": "orange", "[ERROR]": "magenta",
                            "[GS_LOGIC_ERROR]": "purple"}
        chosen_color = "black"
        for prefix, color in prefix_color_map.items():
            if msg.startswith(prefix):
                chosen_color = color
                break

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_output.append(f"<font color='{chosen_color}'>[{timestamp}] {msg}</font>")
        self.log_output.ensureCursorVisible()

    def on_start_tlm(self):
        current_ip_text = self.cb_ips.currentText()
        selected_sc_name = "All"
        if current_ip_text != "All":
            selected_sc_name = self.gs_logic.get_selected_spacecraft_name(current_ip_text)

        self.gs_logic.start_tlm_system(selected_sc_name)
        self.append_terminal_output(f"[시스템] Telemetry System ({selected_sc_name}) 시작 요청됨.")

    def on_start_cmd(self):
        def handler(line): self.append_terminal_output(f"[CMD] {line}")
        self.gs_logic.start_cmd_system(on_stdout_callback=handler)
        self.append_terminal_output("[시스템] Command System 시작 요청됨.")

    def on_tlm_header_changed(self, txt):
        val = self.DEFAULT_TLM_OFFSET
        if txt == '1':
            val = GroundSystemLogic.TLM_HDR_V1_OFFSET
        elif txt == '2':
            val = GroundSystemLogic.TLM_HDR_V2_OFFSET
        else:
            val = self.sb_tlm_offset.value()
        self.sb_tlm_offset.setValue(val)
        self.sb_tlm_offset.setEnabled(txt == "Custom")
        self._save_settings()

    def on_tlm_offset_changed(self, v):
        if self.cb_tlm_header.currentText() == "Custom":
            self._save_settings()

    def on_cmd_header_changed(self, txt):
        pri_val = self.DEFAULT_CMD_OFFSET_PRI
        sec_val = self.DEFAULT_CMD_OFFSET_SEC
        if txt == '1':
            pri_val = GroundSystemLogic.CMD_HDR_PRI_V1_OFFSET
            sec_val = GroundSystemLogic.CMD_HDR_SEC_V1_OFFSET
        elif txt == '2':
            pri_val = GroundSystemLogic.CMD_HDR_PRI_V2_OFFSET
            sec_val = GroundSystemLogic.CMD_HDR_SEC_V2_OFFSET
        else:
            pri_val = self.sb_cmd_pri.value()
            sec_val = self.sb_cmd_sec.value()

        self.sb_cmd_pri.setValue(pri_val)
        self.sb_cmd_sec.setValue(sec_val)
        self.sb_cmd_pri.setEnabled(txt == "Custom")
        self.sb_cmd_sec.setEnabled(txt == "Custom")
        self._save_settings()

    def on_cmd_offset_pri_changed(self, v):
        if self.cb_cmd_header.currentText() == "Custom":
            self._save_settings()

    def on_cmd_offset_sec_changed(self, v):
        if self.cb_cmd_header.currentText() == "Custom":
            self._save_settings()

    def on_ip_list_updated(self, ip, name):
        found = False
        for i in range(self.cb_ips.count()):
            if self.cb_ips.itemData(i) == ip:
                found = True
                break
        if not found:
            self.cb_ips.addItem(f"{name} ({ip})", userData=ip)
        self.append_terminal_output(f"[시스템] IP 목록 업데이트: {name} ({ip})")

    def init_routing_service(self):
        self.gs_logic.init_routing_service()
        if self.gs_logic.routing_service and hasattr(self.gs_logic.routing_service, 'signal_update_ip_list'):
            self.gs_logic.routing_service.signal_update_ip_list.connect(self.on_ip_list_updated)

    # -------------------- test2 연동 보조 --------------------
    def _is_test2_running(self):
        try:
            return (self.test2_process is not None) and (self.test2_process.poll() is None)
        except Exception:
            return False

    def _start_test2(self, cfg_path: pathlib.Path):
        test2_path = self.ROOTDIR / "test2.py"
        if not test2_path.is_file():
            self.append_terminal_output("[오류] test2.py를 찾을 수 없습니다.")
            return
        env = os.environ.copy()
        env["TEST2_CONFIG"] = str(cfg_path)  # 옵션: 환경변수로도 전달
        try:
            # 인자 없이 실행! test2는 설정 파일을 자동 로드함
            self.test2_process = subprocess.Popen(
                ["python3", "-u", str(test2_path)],
                cwd=str(self.ROOTDIR),
                env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            self.append_terminal_output("[시스템] test2 실행 시작 (인자 없이 설정 자동 로드).")
        except Exception as e:
            self.append_terminal_output(f"[오류] test2 실행 실패: {e}")

    def _update_test2_runtime(self, params: dict):
        # 컨트롤 UDP로 즉시 반영
        ip = params.get("ctrl_bind_ip", "127.0.0.1")
        port = int(params.get("ctrl_port", 9696))
        msg = {"cmd":"set", "params": params}
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.5)
            sock.sendto(json.dumps(msg).encode("utf-8"), (ip, port))
            try:
                _ = sock.recvfrom(1024)  # 응답 대기(옵션)
            except socket.timeout:
                pass
            sock.close()
            self.append_terminal_output("[시스템] test2 런타임 파라미터 업데이트 전송 완료.")
        except Exception as e:
            self.append_terminal_output(f"[오류] test2 업데이트 실패: {e}")

    def closeEvent(self, event):
        self.append_terminal_output("[시스템] 종료 중... 모든 설정을 저장합니다.")
        self._save_settings()

        # test2 종료 시도(선택)
        try:
            if self.test2_process and self.test2_process.poll() is None:
                self.test2_process.terminate()
        except Exception:
            pass

        self.gs_logic.stop_cmd_system()
        if self.gs_logic.routing_service and hasattr(self.gs_logic.routing_service, 'stop'):
            self.gs_logic.routing_service.stop()

        print("[시스템] 모든 관련 프로세스 종료 시도 완료. GUI를 닫습니다.")
        super().closeEvent(event)


def main():
    try:
        from _version import __version__, _version_string
        print(_version_string)
    except ImportError:
        print("Version information (_version.py) not found.")

    app = QApplication(sys.argv)
    window = NextGenGroundSystem()
    window.show()
    window.raise_()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

