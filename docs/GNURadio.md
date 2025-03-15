# GNU Radio를 활용한 위성 통신 시뮬레이션

GNU Radio는 소프트웨어 정의 라디오(Software Defined Radio, SDR)를 구현할 수 있는 오픈 소스 개발 프레임워크이다. 신호 처리 블록들을 조합하여 무선 통신 시스템을 시뮬레이션할 수 있다.

## 위성 처리에서의 GNU Radio 활용

- 실제 위성 데이터 스트림을 디코딩하고, 실시간 처리가 가능하다.
- 다양한 변조 방식이 구현 가능하다.
- 도플러 효과와 같이 위성 통신에서 중요한 환경 요소의 영향을 시뮬레이션할 수 있다.
- 여러 개의 위성이 협력하는 네트워크 환경을 소프트웨어적으로 구축 가능하다.
- 실제 SDR 하드웨어와 연동하여 위성 신호를 직접 수신하고 분석할 수 있다.
- NOAA, METEOR, QO-100과 같은 실제 운용 중인 위성 신호를 수신하여 데이터를 분석할 수 있다.

## 대표적인 위성 통신 사용 블록

1. **HackRF Source/Sink** 블록을 통해 신호를 송수신
2. **다양한 변조 블록을 통한 디지털 변조**
    - **BPSK Mod / QPSK Mod**: 위성 통신에서 가장 많이 사용되는 변조 방식
    - **GMSK Mod**: 저속 데이터 전송용 위성에서 사용됨
    - **OFDM Mod**: 넓은 대역을 사용하는 위성에 적용 가능
    - **AM/FM Mod**: NOAA 기상위성 등의 신호를 수신할 때 사용됨
3. **위성 신호의 잡음 제거를 위한 필터 블록**
4. **Doppler Shift Correction 블록**: 위성의 이동으로 인해 발생하는 도플러 효과 보정
5. **패킷 처리 및 디코딩을 위한 Packet Decoder 블록**
6. **다양한 모니터링 블록**
    - **FFT Sink**: 주파수 스펙트럼을 실시간으로 확인하는 블록
    - **Scope Sink**: 신호의 시간 영역(Time Domain) 변화를 모니터링
    - **Constellation Sink**: 디지털 변조 신호의 심볼을 시각화

## HackRF 위성 통신 시뮬레이션 시나리오

1. 각 **HackRF**는 위성 또는 지상국 역할을 수행함
2. 위성 역할의 **HackRF**가 가상의 데이터를 전송함
3. 지상국 역할의 **HackRF**가 데이터를 수신 후 복조하여 확인함

### 위성 HackRF 블록 구성

```
[Random Source] → [BPSK Modulator] → [Root Raised Cosine Filter] → [HackRF Sink]
```

1. **Random Source**: 가상의 랜덤 위성 데이터 생성
2. **BPSK Modulator**: 위상을 변조
3. **RRC 필터**: 대역폭 효율 개선 및 신호 간섭 제거
4. **HackRF Sink**: RF 신호 송신

### 지상국 HackRF 블록 구성

```
[HackRF Source] → [Band-Pass Filter] → [BPSK Demodulator] → [Clock Recovery] → [Packet Decoder]
```

1. **HackRF Source**: 데이터를 수신
2. **Band-Pass Filter**: 잡음 제거
3. **BPSK Demodulator**: 데이터 복조
4. **Clock Recovery**: 동기화 (안정적인 데이터 복원)
5. **Packet Decoder**: 패킷 단위 변환 및 최종 데이터 출력

## 논문에서 사용된 GNU Radio 및 Gr-Leo 기반 저궤도 위성 통신 환경 시뮬레이션

데이터 송수신, 채널 모델링, 신호 처리 및 시각화 과정을 수행하며, 각 블록은 통신 과정의 특정 기능을 담당하여 통신 성능 분석 및 검증에 활용됨.

### 데이터 입력 및 패킷 포맷팅

- **File Source** 블록을 통해 입력 파일에서 데이터를 읽어 테스트 데이터 스트림 생성
- **Protocol Formatter** 블록에서 전송 데이터를 포맷팅하여 헤더를 생성하고 패킷 구조 정의
- **Tagged Stream Mux** 블록을 통해 헤더와 페이로드 결합하여 완전한 패킷 데이터 구성

### 송신 과정

- **Constellation Modulator** 블록을 통해 QPSK 변조 수행
- **Channel Model** 블록을 통해 자유 공간 경로 손실, 잡음 전압, 주파수 오프셋 등의 장애 요소를 시뮬레이션

### 신호 처리 및 복원

- **Polyphase Clock Sync** 블록을 통해 샘플링 타이밍 동기화
- **Costas Loop** 블록을 통해 위상 정보를 복구하여 데이터 손실 방지
- **Linear Equalizer** 블록을 통해 채널 왜곡 보정
- **Constellation Decoder** 블록을 통해 디지털 데이터 변환
- **Correlate Access Code - Tag Stream** 블록을 사용하여 접근 코드(Access Code) 기반 데이터 패킷 식별

### 데이터 검증 및 처리

- **Data Rate Calculator** 블록을 활용하여 전송 데이터 속도를 계산하고 성능 평가 수행

### 시각화 및 출력

- **QT GUI Sink 및 QT GUI Time Sink** 블록을 사용하여 시간 및 주파수 도메인에서 신호를 관찰하며, 시뮬레이션 동안 신호 변화와 특성을 분석 가능함

### 신호 모니터링 블록 활용 예시

| 블록 이름 | 설명 | 활용 예시 |
|-----------|------|------------|
| **FFT Sink** | 주파수 스펙트럼을 실시간으로 확인 | NOAA 위성 신호 수신 상태 확인 |
| **Scope Sink** | 신호의 시간 영역 변화를 모니터링 | 신호 왜곡 여부 확인 |
| **Constellation Sink** | 디지털 변조 신호의 심볼을 시각화 | BPSK, QPSK 변조 신호 확인 |
