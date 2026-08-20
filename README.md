# ECO-Cargo AI

전남 물류/에너지 페르소나(정기철 기사, 50세)를 위한 화물차 전용 유가·경로 관제 AI 프로토타입입니다.
공공 API(오피넷, 도로공사, 기상청)를 연동하여 최저가 경유 주유소, 화물차 휴게소, 실시간 기상 정보를
고대비 HUD 다크모드 대시보드로 제공하며, API 장애 시 0.1초 내 로컬 데이터로 전환되는 Fallback
로직을 갖추고 있습니다.

- 2026 호남IS 코딩챌린지 출품작 (참가번호: HC-000)

## 주요 기능
- 오피넷 실시간 유가 정보 기반 최저가 경유 주유소 탐색
- 월 유류비 절감액 원화(₩) 자동 계산
- 한국도로공사 휴게소/교통 정보 (대형 화물차 주차 대수, 혼잡도)
- 기상청 실시간 기상 정보 및 주의보 안내
- Folium 기반 다크 테마 지도에 최적 경로 및 주유소·휴게소 핀 시각화
- 음성(STT) 브리핑 재생 시뮬레이션
- 공공 API 장애/지연 시 0.1초 내 로컬 데이터 Fallback

## 디렉토리 구조
```
IScodingChallange/
├── app.py                # Streamlit 메인 애플리케이션
├── requirements.txt      # Python 의존성 목록
├── prompt_history.md     # 대회 제출용 프롬프트 이력서
├── gamma_slides.md       # Gamma AI용 발표자료 스크립트 (12페이지)
└── README.md             # 프로젝트 설명 (본 파일)
```

## 설치 및 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경변수(API 키) 설정
공공데이터포털(data.go.kr), 한국도로공사, 카카오 디벨로퍼스에서 발급받은 API 키를 환경변수로 설정합니다.
API 키가 없어도 앱은 정상 동작하며(로컬 Fallback 데이터 사용), 실시간 데이터를 받으려면
아래 값을 설정하세요.

**Windows PowerShell:**
```powershell
$env:OPINET_API_KEY="발급받은_오피넷_API_키"
$env:STATION_API_KEY="발급받은_도로공사_주유소현황_API_키"
$env:EX_API_KEY="발급받은_도로공사_휴게소_API_키"
$env:KMA_API_KEY="발급받은_기상청_API_키"
$env:KAKAO_REST_API_KEY="발급받은_카카오_REST_API_키"
```

**macOS / Linux (bash):**
```bash
export OPINET_API_KEY="발급받은_오피넷_API_키"
export STATION_API_KEY="발급받은_도로공사_주유소현황_API_키"
export EX_API_KEY="발급받은_도로공사_휴게소_API_키"
export KMA_API_KEY="발급받은_기상청_API_키"
export KAKAO_REST_API_KEY="발급받은_카카오_REST_API_키"
```

또는 프로젝트 루트에 `.env` 파일을 만들어 관리할 수도 있습니다(별도 로더 도입 시).

> ⚠️ `app.py`에는 데모/제출용 기본 키 값이 코드에 남아 있습니다. 공개 저장소에 올리기 전에는
> 반드시 제거하고 환경변수로만 관리하세요. 또한 카카오 앱에서 "OPEN_MAP_AND_LOCAL"(로컬 API)
> 권한이 비활성화된 경우, 코드 내 `KAKAO_KNOWN_PLACES` 사전에 없는 지명은 좌표 변환에 실패해
> Fallback 경로로 전환됩니다. 카카오 디벨로퍼스 콘솔에서 해당 권한을 활성화하면 모든 지명에
> 대해 실시간 길찾기가 동작합니다.

### 3. 앱 실행
```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속하면 대시보드를 확인할 수 있습니다.

## API 키 미설정 시 동작
`OPINET_API_KEY`, `EX_API_KEY`, `KMA_API_KEY` 중 하나라도 설정되지 않으면 해당 데이터는
자동으로 전남 지역 기준 로컬 Fallback 데이터(하드코딩된 샘플)로 대체되어, 네트워크나 API 키
발급 여부와 무관하게 항상 시연 가능합니다.

## 데이터 출처
- [오피넷(OPINET)](https://www.opinet.co.kr) — 실시간 유가 정보
- [한국도로공사 공공데이터](https://data.ex.co.kr) — 휴게소/교통 정보
- [기상청 공공데이터포털](https://www.data.go.kr) — 실시간 기상 정보
