import socket

# 수신할 IP와 포트 설정 (0.0.0.0은 모든 인터페이스에서 수신)
LISTEN_IP = '0.0.0.0'
LISTEN_PORT = 50000

# 전송 대상 IP와 포트 설정 (예: 로컬호스트의 다른 포트)
DEST_IP = '127.0.0.1'
DEST_PORT = 1234

# UDP 소켓 생성 (수신용)
sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_in.bind((LISTEN_IP, LISTEN_PORT))

# UDP 소켓 생성 (전송용)
sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Listening on {LISTEN_IP}:{LISTEN_PORT} ...")
while True:
    data, addr = sock_in.recvfrom(4096)  # 최대 4096 바이트까지 수신
    print(f"Received {len(data)} bytes from {addr}")
    # 수신한 데이터를 대상 IP와 포트로 전송
    sock_out.sendto(data, (DEST_IP, DEST_PORT))
    print(f"Forwarded data to {DEST_IP}:{DEST_PORT}")

