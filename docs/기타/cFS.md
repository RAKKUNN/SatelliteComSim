​core Flight System(cFS)는 NASA에서 개발한 플랫폼 독립적인 재사용 가능한 소프트웨어 프레임워크로, 우주 비행 소프트웨어 개발을 가속화하기 위해 설계됨
이 시스템은 우주 비행체 소프트웨어 개발을 표준화하고 재사용 가능하게 만들기 위해 NASA에서 만든 오픈소스 모듈형 임베디드 비행 소프트웨어 프레임워크

구성 요소 (Architecture)
cFS는 세 가지 주요 계층으로 구성

1. Operating System Abstraction Layer (OSAL)
다양한 RTOS(Real-Time Operating System)에 대해 공통 인터페이스를 제공
예를 들어, VxWorks, RTEMS, POSIX 시스템을 모두 지원
OS에 종속되지 않도록 소프트웨어 이식성 확보

2. Platform Support Package (PSP)
하드웨어에 종속적인 인터페이스 제공
예: 타이머, 메모리, I/O 장치 드라이버
하나의 애플리케이션을 여러 하드웨어에 맞게 쉽게 포팅 가능

3. Core Flight Executive (cFE)
비행 소프트웨어의 핵심 서비스를 제공
주요 기능: Task scheduling, Inter-process communication (message bus), Time management, Event service, Software bus (Pub/Sub 방식), Table management

이 계층 덕분에 **cFS는 이식성(portability)**이 아주 높고, 하드웨어/OS가 달라도 앱 재사용이 가능
