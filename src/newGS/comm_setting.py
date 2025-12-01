#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox, QLineEdit,
    QDoubleSpinBox, QSpinBox, QComboBox
)

class CommSettingsDialog(QDialog):
    def __init__(self, parent=None, defaults=None):
        super().__init__(parent)
        self.setWindowTitle("통신 설정")
        layout = QFormLayout(self)

        d = defaults or {}
        # 네트워크
        self.le_listen_ip  = QLineEdit(d.get("listen_ip", "0.0.0.0"))
        self.sb_listen_port= QSpinBox(); self.sb_listen_port.setRange(1,65535); self.sb_listen_port.setValue(d.get("listen_port",8600))
        self.le_dst_ip     = QLineEdit(d.get("dst_ip","127.0.0.1"))
        self.sb_dst_port   = QSpinBox(); self.sb_dst_port.setRange(1,65535); self.sb_dst_port.setValue(d.get("dst_port",1234))
        self.sb_mtu        = QSpinBox(); self.sb_mtu.setRange(256,65535); self.sb_mtu.setValue(d.get("mtu",1472))
        self.le_ctrl_ip    = QLineEdit(d.get("ctrl_bind_ip","127.0.0.1"))
        self.sb_ctrl_port  = QSpinBox(); self.sb_ctrl_port.setRange(1,65535); self.sb_ctrl_port.setValue(d.get("ctrl_port",9696))

        layout.addRow("Listen IP",  self.le_listen_ip)
        layout.addRow("Listen Port",self.sb_listen_port)
        layout.addRow("Dest IP",    self.le_dst_ip)
        layout.addRow("Dest Port",  self.sb_dst_port)
        layout.addRow("MTU",        self.sb_mtu)
        layout.addRow("Ctrl Bind IP", self.le_ctrl_ip)
        layout.addRow("Ctrl Port",    self.sb_ctrl_port)

        # 우주환경
        self.ds_delay  = QDoubleSpinBox(); self.ds_delay.setRange(0, 1e6); self.ds_delay.setDecimals(3); self.ds_delay.setValue(d.get("base_delay_ms",0.0)); self.ds_delay.setSuffix(" ms")
        self.ds_jitter = QDoubleSpinBox(); self.ds_jitter.setRange(0, 1e6); self.ds_jitter.setDecimals(3); self.ds_jitter.setValue(d.get("jitter_ms",0.0)); self.ds_jitter.setSuffix(" ms")
        self.ds_ber    = QDoubleSpinBox(); self.ds_ber.setRange(0,1); self.ds_ber.setDecimals(10); self.ds_ber.setValue(d.get("ber",0.0))
        self.sb_seed   = QSpinBox(); self.sb_seed.setRange(0, 2**31-1); self.sb_seed.setValue(d.get("seed",0xBEEF))
        self.cb_mode   = QComboBox(); self.cb_mode.addItems(["payload_only","full"])
        self.cb_mode.setCurrentText(d.get("mode","payload_only"))

        layout.addRow("Delay",  self.ds_delay)
        layout.addRow("Jitter", self.ds_jitter)
        layout.addRow("BER",    self.ds_ber)
        layout.addRow("Seed",   self.sb_seed)
        layout.addRow("Mode",   self.cb_mode)

        # SAMPLE_APP 텍스트 오프셋
        self.sb_len_off  = QSpinBox(); self.sb_len_off.setRange(0,4096); self.sb_len_off.setValue(d.get("tlm08a9_len_off",12))
        self.sb_text_off = QSpinBox(); self.sb_text_off.setRange(0,4096); self.sb_text_off.setValue(d.get("tlm08a9_text_off",14))
        self.sb_text_max = QSpinBox(); self.sb_text_max.setRange(0,65535); self.sb_text_max.setValue(d.get("tlm08a9_text_max",128))
        layout.addRow("TextLen Off", self.sb_len_off)
        layout.addRow("Text Off",    self.sb_text_off)
        layout.addRow("Text Max",    self.sb_text_max)

        btns = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get(self):
        return {
            "listen_ip": self.le_listen_ip.text(),
            "listen_port": self.sb_listen_port.value(),
            "dst_ip": self.le_dst_ip.text(),
            "dst_port": self.sb_dst_port.value(),
            "mtu": self.sb_mtu.value(),
            "ctrl_bind_ip": self.le_ctrl_ip.text(),
            "ctrl_port": self.sb_ctrl_port.value(),
            "base_delay_ms": float(self.ds_delay.value()),
            "jitter_ms": float(self.ds_jitter.value()),
            "ber": float(self.ds_ber.value()),
            "seed": int(self.sb_seed.value()),
            "mode": self.cb_mode.currentText(),
            "tlm08a9_len_off": self.sb_len_off.value(),
            "tlm08a9_text_off": self.sb_text_off.value(),
            "tlm08a9_text_max": self.sb_text_max.value(),
        }

