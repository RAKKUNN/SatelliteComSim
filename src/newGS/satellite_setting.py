#!/usr/bin/env python3
# satellite_setting.py

from PyQt5.QtWidgets import QDialog, QFormLayout, QComboBox, QDoubleSpinBox, QDialogButtonBox

class SatelliteSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("위성 파라미터 설정")
        self.setModal(True)
        layout = QFormLayout(self)
        
        # 위성 종류
        self.cb_sat_type = QComboBox()
        self.cb_sat_type.addItems(["소형 위성", "중형 위성", "대형 위성"])
        layout.addRow("위성 종류", self.cb_sat_type)
        
        # 위성 크기 (반지름)
        self.ds_sat_size = QDoubleSpinBox()
        self.ds_sat_size.setRange(1.0, 50.0)
        self.ds_sat_size.setValue(10.0)
        self.ds_sat_size.setSuffix(" units")
        layout.addRow("위성 크기", self.ds_sat_size)
        
        # 위성 속도 (radian/sec)
        self.ds_sat_speed = QDoubleSpinBox()
        self.ds_sat_speed.setRange(0.0, 1.0)
        self.ds_sat_speed.setDecimals(3)
        self.ds_sat_speed.setValue(0.05)
        layout.addRow("위성 속도", self.ds_sat_speed)
        
        # 궤도 높이 (반지름)
        self.ds_orbital_radius = QDoubleSpinBox()
        self.ds_orbital_radius.setRange(50.0, 500.0)
        self.ds_orbital_radius.setValue(300.0)
        self.ds_orbital_radius.setSuffix(" units")
        layout.addRow("궤도 높이", self.ds_orbital_radius)
        
        # 궤도 경사각 (degrees)
        self.ds_inclination = QDoubleSpinBox()
        self.ds_inclination.setRange(0.0, 90.0)
        self.ds_inclination.setValue(45.0)
        self.ds_inclination.setSuffix(" °")
        layout.addRow("궤도 경사각", self.ds_inclination)
        
        # 이심률 (eccentricity)
        self.ds_eccentricity = QDoubleSpinBox()
        self.ds_eccentricity.setRange(0.0, 1.0)
        self.ds_eccentricity.setDecimals(2)
        self.ds_eccentricity.setValue(0.0)
        layout.addRow("이심률", self.ds_eccentricity)
        
        # 신호 주파수 (GHz)
        self.ds_frequency = QDoubleSpinBox()
        self.ds_frequency.setRange(0.1, 10.0)
        self.ds_frequency.setDecimals(2)
        self.ds_frequency.setValue(2.4)
        self.ds_frequency.setSuffix(" GHz")
        layout.addRow("신호 주파수", self.ds_frequency)
        
        # 안테나 이득 (dBi)
        self.ds_antenna_gain = QDoubleSpinBox()
        self.ds_antenna_gain.setRange(0.0, 30.0)
        self.ds_antenna_gain.setValue(10.0)
        self.ds_antenna_gain.setSuffix(" dBi")
        layout.addRow("안테나 이득", self.ds_antenna_gain)
        
        # 송신 전력 (dBm)
        self.ds_transmit_power = QDoubleSpinBox()
        self.ds_transmit_power.setRange(-30.0, 30.0)
        self.ds_transmit_power.setValue(0.0)
        self.ds_transmit_power.setSuffix(" dBm")
        layout.addRow("송신 전력", self.ds_transmit_power)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    
    def getParameters(self):
        return {
            "sat_type": self.cb_sat_type.currentText(),
            "sat_size": self.ds_sat_size.value(),
            "sat_speed": self.ds_sat_speed.value(),
            "orbital_radius": self.ds_orbital_radius.value(),
            "inclination": self.ds_inclination.value(),
            "eccentricity": self.ds_eccentricity.value(),
            "frequency": self.ds_frequency.value(),
            "antenna_gain": self.ds_antenna_gain.value(),
            "transmit_power": self.ds_transmit_power.value()
        }
