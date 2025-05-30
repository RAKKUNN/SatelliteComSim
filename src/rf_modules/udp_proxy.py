# src/rf_modules/udp_proxy.py
import socket
import json
from typing import Optional, Tuple, Callable
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QObject

class UDPLink(QThread):
    """UDP 통신을 처리하는 QThread 기반 클래스"""
    data_received = pyqtSignal(bytes, tuple)  # (data, addr)
    status_updated = pyqtSignal(str)

    def __init__(self, listen_port: int = 50003, 
                 target_ip: str = "127.0.0.1",
                 target_port: int = 50004,
                 parent: QObject = None):
        super().__init__(parent)
        self.listen_port = listen_port
        self.target_ip = target_ip
        self.target_port = target_port
        self.socket = None
        self.running = False

    def run(self):
        """스레드 실행 메서드"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.settimeout(1.0)
            self.socket.bind(('0.0.0.0', self.listen_port))
            self.running = True
            self.status_updated.emit(f"UDP 서버 시작됨 (포트: {self.listen_port})")
            
            while self.running:
                try:
                    data, addr = self.socket.recvfrom(4096)
                    if data:
                        self.data_received.emit(data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.status_updated.emit(f"수신 오류: {str(e)}")
                    break
                    
        except Exception as e:
            self.status_updated.emit(f"UDP 서버 오류: {str(e)}")
        finally:
            if self.socket:
                self.socket.close()
            self.status_updated.emit("UDP 서버 중지됨")

    def send_data(self, data: bytes) -> bool:
        """데이터 전송"""
        if not self.socket:
            self.status_updated.emit("소켓이 초기화되지 않았습니다")
            return False
        
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            self.socket.sendto(data, (self.target_ip, self.target_port))
            return True
        except Exception as e:
            self.status_updated.emit(f"전송 실패: {str(e)}")
            return False

    def stop(self):
        """스레드 정지"""
        self.running = False
        self.wait()  # 스레드가 완전히 종료될 때까지 대기


class UDPProxy(QObject):
    """
    UDP 프록시 서버로, GroundSystem과 GNU Radio 모듈 간의 중계를 담당합니다.
    QObject를 상속받아 Qt 이벤트 루프와 호환되도록 합니다.
    """
    status_updated = pyqtSignal(str)

    def __init__(self, gs_port: int = 50000, 
                 tx_port: int = 52003, 
                 rx_port: int = 50004,
                 proxy_ip: str = "0.0.0.0",
                 parent: QObject = None):
        super().__init__(parent)
        self.gs_port = gs_port
        self.tx_port = tx_port
        self.rx_port = rx_port
        self.proxy_ip = proxy_ip
        
        # GS <-> Proxy <-> TX/RX 통신을 위한 링크
        self.gs_link = None
        self.rx_link = None
        
        # 마지막으로 알려진 GS 주소
        self.last_gs_addr = None

    def start(self) -> bool:
        """프록시 서버 시작"""
        try:
            # GS로부터 수신할 링크
            self.gs_link = UDPLink(
                listen_port=self.gs_port,
                target_ip="127.0.0.1",
                target_port=self.tx_port
            )
            self.gs_link.data_received.connect(self._on_gs_data)
            self.gs_link.status_updated.connect(self._on_status_updated)
            
            # RX로부터 수신할 링크
            self.rx_link = UDPLink(
                listen_port=self.rx_port,
                target_ip="127.0.0.1",
                target_port=self.gs_port
            )
            self.rx_link.data_received.connect(self._on_rx_data)
            self.rx_link.status_updated.connect(self._on_status_updated)
            
            # 링크 시작
            self.gs_link.start()
            self.rx_link.start()
            
            self.status_updated.emit(
                f"프록시 서버 시작됨 (GS: {self.proxy_ip}:{self.gs_port}, "
                f"TX: 127.0.0.1:{self.tx_port}, RX: {self.proxy_ip}:{self.rx_port})"
            )
            return True
            
        except Exception as e:
            self.status_updated.emit(f"프록시 서버 시작 실패: {str(e)}")
            self.stop()
            return False

    def stop(self) -> None:
        """프록시 서버 중지"""
        if self.gs_link:
            self.gs_link.stop()
            self.gs_link = None
            
        if self.rx_link:
            self.rx_link.stop()
            self.rx_link = None
            
        self.status_updated.emit("프록시 서버 중지됨")

    def _on_gs_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """GS로부터 데이터 수신 시 호출"""
        self.last_gs_addr = addr
        self.status_updated.emit(f"GS로부터 {len(data)}바이트 수신")
        
        # TX로 전달
        if self.gs_link:
            self.gs_link.send_data(data)

    def _on_rx_data(self, data: bytes, addr: Tuple[str, int]) -> None:
        """RX로부터 데이터 수신 시 호출"""
        self.status_updated.emit(f"RX로부터 {len(data)}바이트 수신")
        
        # GS로 전달 (마지막으로 알려진 주소로)
        if self.last_gs_addr and self.gs_link and self.gs_link.socket:
            try:
                self.gs_link.socket.sendto(data, self.last_gs_addr)
            except Exception as e:
                self.status_updated.emit(f"GS 전송 오류: {str(e)}")

    def _on_status_updated(self, message: str) -> None:
        """상태 업데이트 메시지 전달"""
        self.status_updated.emit(message)


# 간단한 테스트 코드
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget, QPushButton
    
    class TestApp(QWidget):
        def __init__(self):
            super().__init__()
            self.init_ui()
            
        def init_ui(self):
            self.setWindowTitle('UDP Proxy 테스트')
            self.setGeometry(100, 100, 600, 400)
            
            layout = QVBoxLayout()
            
            self.log_view = QPlainTextEdit()
            self.log_view.setReadOnly(True)
            layout.addWidget(self.log_view)
            
            self.btn_start = QPushButton('시작')
            self.btn_start.clicked.connect(self.start_proxy)
            layout.addWidget(self.btn_start)
            
            self.btn_stop = QPushButton('중지')
            self.btn_stop.clicked.connect(self.stop_proxy)
            self.btn_stop.setEnabled(False)
            layout.addWidget(self.btn_stop)
            
            self.setLayout(layout)
            
            self.proxy = UDPProxy()
            self.proxy.status_updated.connect(self.log_message)
            
        def log_message(self, message):
            self.log_view.appendPlainText(message)
            
        def start_proxy(self):
            if self.proxy.start():
                self.btn_start.setEnabled(False)
                self.btn_stop.setEnabled(True)
                
        def stop_proxy(self):
            self.proxy.stop()
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            
        def closeEvent(self, event):
            self.proxy.stop()
            event.accept()
    
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec_())
