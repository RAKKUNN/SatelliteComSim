import socket

LISTEN_IP = '0.0.0.0'
LISTEN_PORT = 50000

DEST_IP = '127.0.0.1'
DEST_PORT = 1234


sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_in.bind((LISTEN_IP, LISTEN_PORT))


sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Listening on {LISTEN_IP}:{LISTEN_PORT} ...")
while True:
    data, addr = sock_in.recvfrom(4096)  
    print(f"Received {len(data)} bytes from {addr}")
    
    sock_out.sendto(data, (DEST_IP, DEST_PORT))
    print(f"Forwarded data to {DEST_IP}:{DEST_PORT}")

