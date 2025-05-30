#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import signal
import subprocess
import argparse
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, QObject, pyqtSignal

class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.setToolTip('Satellite Communication Simulator')
        
        # Create menu
        self.menu = QMenu(parent)
        
        # Status actions
        self.status_action = self.menu.addAction("Status: Starting...")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        
        # Component actions
        self.components = {
            'gs': {'name': 'Ground System', 'process': None, 'action': None, 'cmd': None},
            'udp': {'name': 'UDP Proxy', 'process': None, 'action': None, 'cmd': None},
            'tx': {'name': 'TX Flow', 'process': None, 'action': None, 'cmd': None},
            'rx': {'name': 'RX Flow', 'process': None, 'action': None, 'cmd': None}
        }
        
        for comp_id, comp in self.components.items():
            comp['action'] = self.menu.addAction(f"Stop {comp['name']}")
            comp['action'].setEnabled(False)
            comp['action'].triggered.connect(lambda checked, cid=comp_id: self.toggle_component(cid))
        
        self.menu.addSeparator()
        # Exit action
        exit_action = self.menu.addAction("Exit")
        exit_action.triggered.connect(self.exit_application)
        
        self.setContextMenu(self.menu)
        self.activated.connect(self.on_tray_icon_activated)
        
        # Set default status
        self.update_status("Starting system components...")
    
    def set_commands(self, commands):
        """Set the commands for each component"""
        for comp_id, cmd in commands.items():
            if comp_id in self.components:
                self.components[comp_id]['cmd'] = cmd
    
    def start_components(self):
        """Start all components"""
        for comp_id in self.components:
            self.start_component(comp_id)
    
    def start_component(self, comp_id):
        """Start a specific component"""
        comp = self.components[comp_id]
        if comp['process'] is None and comp['cmd']:
            try:
                # 현재 작업 디렉토리 저장
                cwd = os.getcwd()
                
                # 명령어와 작업 디렉토리 분리
                cmd_parts = comp['cmd'].split()
                script_path = cmd_parts[1].strip('"\'')
                script_dir = os.path.dirname(script_path)
                script_name = os.path.basename(script_path)
                
                # 작업 디렉토리 변경
                if script_dir:
                    os.chdir(script_dir)
                
                # 명령어 재구성 (현재 디렉토리 기준)
                cmd = f'"{sys.executable}" "{script_name}"'
                
                # 프로세스 시작
                comp['process'] = subprocess.Popen(
                    cmd,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
                
                # 원래 디렉토리로 복원
                os.chdir(cwd)
                
                comp['action'].setText(f"Stop {comp['name']}")
                comp['action'].setEnabled(True)
                self.showMessage(
                    "System Notification",
                    f"{comp['name']} started successfully",
                    QSystemTrayIcon.Information,
                    2000
                )
                return True
            except Exception as e:
                self.showMessage(
                    "Error",
                    f"Failed to start {comp['name']}: {str(e)}",
                    QSystemTrayIcon.Critical,
                    5000
                )
                return False
        return False
    
    def stop_component(self, comp_id):
        """Stop a specific component"""
        comp = self.components[comp_id]
        if comp['process']:
            try:
                if os.name == 'nt':
                    import ctypes
                    ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)
                else:
                    comp['process'].send_signal(signal.SIGINT)
                
                # Wait for process to terminate
                try:
                    comp['process'].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    comp['process'].terminate()
                    comp['process'].wait(timeout=2)
                
                comp['process'] = None
                comp['action'].setText(f"Start {comp['name']}")
                self.showMessage(
                    "System Notification",
                    f"{comp['name']} stopped",
                    QSystemTrayIcon.Information,
                    2000
                )
                return True
            except Exception as e:
                self.showMessage(
                    "Error",
                    f"Failed to stop {comp['name']}: {str(e)}",
                    QSystemTrayIcon.Critical,
                    5000
                )
                return False
        return False
    
    def toggle_component(self, comp_id):
        """Toggle component start/stop"""
        comp = self.components[comp_id]
        if comp['process'] is None:
            self.start_component(comp_id)
        else:
            self.stop_component(comp_id)
    
    def update_status(self, message):
        """Update status message"""
        self.status_action.setText(f"Status: {message}")
    
    def on_tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_status()
    
    def show_status(self):
        """Show status window"""
        status_msg = "Satellite Communication Simulator\n\n"
        status_msg += "Components Status:\n"
        
        for comp_id, comp in self.components.items():
            status = "Running" if comp['process'] else "Stopped"
            status_msg += f"- {comp['name']}: {status}\n"
        
        QMessageBox.information(None, "System Status", status_msg)
    
    def exit_application(self):
        """Clean up and exit application"""
        # Stop all components
        for comp_id in self.components:
            if self.components[comp_id]['process']:
                self.stop_component(comp_id)
        
        # Exit application
        QApplication.quit()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Satellite Communication Simulator')
    parser.add_argument('--no-gui', action='store_true', help='Run without GUI')
    args = parser.parse_args()
    
    # 현재 디렉토리 기준으로 상대 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create system tray icon (상대 경로로 아이콘 로드)
    icon_path = os.path.join(current_dir, 'newGS', 'textures', 'satellite_texture.jpg')
    if not os.path.exists(icon_path):
        icon = QIcon.fromTheme('network-transmit-receive')
    else:
        icon = QIcon(icon_path)
    
    tray_icon = SystemTrayIcon(icon)
    
    # 상대 경로를 사용하여 컴포넌트 명령어 정의
    component_commands = {
        'gs': f'"{sys.executable}" "{os.path.join(current_dir, "newGS", "GroundSystem.py")}"',
        'udp': f'"{sys.executable}" "{os.path.join(current_dir, "rf_modules", "udp_proxy.py")}"',
        'tx': f'"{sys.executable}" "{os.path.join(current_dir, "rf_modules", "tx_flow.py")}"',
        'rx': f'"{sys.executable}" "{os.path.join(current_dir, "rf_modules", "rx_flow.py")}"'
    }
    
    # Set commands and start components
    tray_icon.set_commands(component_commands)
    
    if not args.no_gui:
        tray_icon.show()
        tray_icon.showMessage(
            "Satellite Com Simulator",
            "Starting system components...",
            QSystemTrayIcon.Information,
            3000
        )
    
    # Start all components
    tray_icon.start_components()
    
    # Show main window if not in tray-only mode
    if not args.no_gui:
        # Add current directory to Python path
        sys.path.insert(0, current_dir)
        
        # Set environment variable for texture paths
        os.environ['TEXTURE_PATH'] = os.path.join(current_dir, 'newGS', 'textures')
        
        from newGS.GroundSystem import NextGenGroundSystem
        main_window = NextGenGroundSystem()
        main_window.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
