# CCSDS(Consultative Committee for Space Data Systems)

위성과 지상국 간의 데이터 전송 표준을 정의하는 국제적인 기구

![스크린샷 2025-03-12 154514](https://github.com/user-attachments/assets/93de19b5-de7f-409d-a09c-eef7a3d71622)

### **1️⃣ 물리 계층 (Physical Layer)**

- **RF/Optical (무선/광학 통신)**
    - 위성과 지상국 간 데이터 전송을 위한 실제 신호 전송 매체.
    - **RF(Radio Frequency) 또는 Optical(레이저 기반 통신) 사용**.
- **Wire (유선 통신)**
    - 지상 시스템 간 데이터 전송에 사용.

### **2️⃣ 데이터 링크 계층 (Data Link Layer)**

위성과 지상국 간의 데이터 링크를 담당하는 프로토콜.

- **USLP (Unified Space Link Protocol)**
    - CCSDS의 최신 표준으로, 기존 TM, TC, AOS 프로토콜을 통합한 프로토콜.
- **TM (Telemetry)**
    - 위성이 지상국으로 데이터를 보내는 원격 측정(telemetry) 프로토콜.
- **TC (Telecommand)**
    - 지상국이 위성에 명령을 전송하는 프로토콜.
- **AOS (Advanced Orbiting Systems)**
    - 다중 사용자 데이터를 처리하는 고급 위성 데이터 링크 프로토콜.
- **Prox-1 (Proximity-1 Protocol)**
    - 저궤도(LEO) 및 근거리 위성 간 통신을 위한 프로토콜.

### **3️⃣ 네트워크 계층 및 전송 계층**

- **Either Encapsulation Packet Protocol or Space Packet Protocol**
    - 데이터가 캡슐화(encapsulation)될 수 있는 방식 정의.
- **LTP (Licklider Transmission Protocol)**
    - *딜레이 톨러런트 네트워킹(DTN, Delay-Tolerant Networking)**을 지원하는 프로토콜.
    - 심우주 통신과 같이 신호 지연이 큰 환경에 최적화됨.
- **IPoC (IP over CCSDS)**
    - 위성 네트워크에서 **IP 프로토콜을 사용할 수 있도록 변환**.
- **TCP/UDP 및 IP**
    - 기존 인터넷 프로토콜을 위성 통신에 적용 가능.
    - 위성 인터넷(스타링크 등)에서 사용.

### **4️⃣ 응용 계층 (Upper Layers)**

위성 데이터 전송 및 운영을 담당하는 최상위 계층.

- **CFDP (CCSDS File Delivery Protocol)**
    - 위성에서 데이터를 신뢰성 있게 지상국으로 전송하는 파일 전송 프로토콜.
- **BP (Bundle Protocol)**
    - DTN(Delay-Tolerant Networking) 환경에서 데이터를 패킷 단위로 전송하는 네트워크 프로토콜.
- **SPP (Space Packet Protocol)**
    - CCSDS 패킷 기반 데이터 전송을 위한 표준 프로토콜.
- **MO-MAL (Mission Operations Message Abstraction Layer)**
    - 위성 미션 데이터를 관리하고 표준화하는 프로토콜.
- **AMS (Asynchronous Message Service)**
    - 비동기식 메시지 전달 서비스.

## **📌 CCSDS 프로토콜 구조**

CCSDS에서 만든 프로토콜들은 계층별로 나뉘며, **우주 통신을 위한 국제 표준 프로토콜**로 사용됩니다.

| **계층**         | **CCSDS 프로토콜**                                                         | **설명**                        |
|-----------------|---------------------------------------------------------------------------|--------------------------------|
| **응용 계층**    | **CFDP (CCSDS File Delivery Protocol)**                                  | 위성 데이터 파일 전송          |
|                 | **MO Services (Mission Operations Services)**                            | 위성 운영 메시지 처리          |
| **전송 계층**    | **SCPS-TP (Space Communications Protocol Standards - Transport Protocol)** | TCP/IP 최적화                  |
| **네트워크 계층** | **SCPS-NP (Space Communications Protocol Standards - Network Protocol)**   | 위성 간 네트워크 라우팅        |
|                 | **DTN (Delay-Tolerant Networking)**                                      | 심우주 통신을 위한 네트워크    |
| **데이터 링크 계층** | **TM (Telemetry), TC (Telecommand)**                                  | 원격 측정/명령 데이터 전송     |
|                 | **AOS (Advanced Orbiting Systems)**                                     | 위성 다중 데이터 전송          |
| **물리 계층**    | **CCSDS RF & Modulation**                                              | 위성 신호 변조 및 주파수 할당  |
