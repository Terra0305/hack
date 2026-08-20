# 프롬프트 이력서 (Prompt History)

**참가번호:** HC-000
**프로젝트명:** ECO-Cargo AI
**작성일:** 2026-08-20
**사용 AI 도구:** GitHub Copilot (코드 작성), Gemini (시나리오 검증), Gamma (PPT 시각화)

---

## 1단계 — 데이터 모델링 (Data Modeling)

### 프롬프트 1-1
```
전남 지역 대형 화물차 기사(50세, 정기철)를 위한 서비스를 만들려고 해.
오피넷 유가 API, 도로공사 휴게소 API, 기상청 API에서 받아올 데이터를
하나의 Python dict/DataFrame 구조로 통합 모델링해줘.
필드는 주유소명, 브랜드, 경유가, 위도/경도, 휴게소명, 대형차 주차 대수,
혼잡도, 기상 상태를 포함해야 해. Chain of Thought로 설계 이유도 설명해줘.
```

**AI 답변 요약:**
- 3개 공공 API의 응답 스키마가 서로 다르므로, 공통 필드(name, lat, lon, price/status)로 정규화하는
  중간 계층(FALLBACK_STATIONS, FALLBACK_REST_AREAS, FALLBACK_WEATHER)을 제안.
- 화물차 특화 필드(대형 주차 면수, 경유가)를 우선순위로 배치해 일반 내비게이션 앱과 차별화할 것을 권장.
- pandas DataFrame으로 변환 후 `idxmin()`으로 최저가 탐색, `mean()`으로 평균가 대비 절감액 계산 로직 제안.

### 프롬프트 1-2
```
월 유류비 절감액을 원화(₩)로 계산하는 함수를 설계해줘.
정기철 기사님의 월 평균 주유량(1,500L 가정) 기준으로,
최저가 주유소와 평균가의 차액 * 주유량으로 계산하는 로직이면 될까?
```

**AI 답변 요약:**
- `calc_monthly_savings(monthly_liter, cheapest_price, avg_price)` 함수 제안.
- 음수 방지를 위해 `max(avg_price - cheapest_price, 0)` 처리 필요성 언급.
- 슬라이더 UI로 주유량을 조정 가능하게 하여 실사용자 시뮬레이션 정확도를 높이는 방안 제시.

---

## 2단계 — UI/지도 바이브 코딩 (UI & Map Vibe Coding)

### 프롬프트 2-1
```
50대 야간 운전자가 보기 편한 고대비 다크모드 HUD 대시보드를
Streamlit으로 만들어줘. 폰트 크기는 크게, 배경은 어둡게,
핵심 숫자(절감액, 최저가)는 네온 그린 계열로 강조해줘.
```

**AI 답변 요약:**
- `st.markdown` + 커스텀 CSS(`<style>`)로 `.hud-card`, `.hud-metric` 클래스 정의.
- 배경색 `#0a0f0d`, 강조색 `#39ff14`(네온 그린) 조합으로 시인성 확보.
- 4분할 `st.columns`로 핵심 지표(최저가, 절감액, 기상, API 상태)를 한눈에 보이도록 배치 제안.

### 프롬프트 2-2
```
Folium로 전남 지역 지도를 다크 테마로 띄우고,
최저가 주유소는 초록 핀, 나머지는 회색 핀, 휴게소는 주황 핀으로 표시해줘.
경로선도 하나 그려줘.
```

**AI 답변 요약:**
- `folium.Map(tiles="CartoDB dark_matter")`로 다크 테마 지도 구현.
- `folium.Icon(color=...)`로 조건부 핀 색상 분기(`is_cheapest` 여부로 green/lightgray).
- `folium.PolyLine`으로 주유소 좌표를 연결한 임시 경로선 시각화, `streamlit_folium.st_folium`으로 렌더링.

### 프롬프트 2-3
```
음성 브리핑 재생 버튼을 누르면 STT/TTS를 흉내내는 시뮬레이션으로,
"OO 기사님, 현재 최저가는 ...입니다" 같은 텍스트를 st.success로 보여줘.
```

**AI 답변 요약:**
- `st.session_state`로 버튼 클릭 상태를 저장해 재실행 시에도 유지.
- `time.sleep(0.5)` + `st.spinner`로 실제 음성 생성처럼 로딩 연출.
- f-string으로 실시간 데이터(최저가 주유소명, 가격, 절감액)를 문장에 동적으로 삽입.

---

## 3단계 — 예외처리 및 최적화 (Exception Handling & Optimization)

### 프롬프트 3-1
```
공공 API가 응답 지연되거나 장애가 났을 때, 0.1초 안에 무조건
로컬 하드코딩 데이터로 전환되는 Fallback 로직을 짜줘.
requests 타임아웃 기준으로 구현하고, 실패 사유와 전환 시간을
화면에 표시해줘.
```

**AI 답변 요약:**
- `requests.get(..., timeout=0.1)`로 하드 타임아웃 설정, `try-except Exception`으로 모든 예외
  (Timeout, ConnectionError, JSONDecodeError 등)를 포괄적으로 캐치.
- `time.time()` 측정으로 실제 전환 소요 시간(ms)을 계산해 `"FALLBACK (32ms 내 로컬 데이터 전환)"`
  형태로 상태 문구를 동적으로 생성하는 방식 제안.
- API 키 미설정 상태(`OPINET_API_KEY` 빈 값)도 사전에 `ValueError`로 처리해 개발/테스트 환경에서도
  즉시 Fallback이 동작하도록 설계.

### 프롬프트 3-2
```
API 키가 없는 로컬 개발 환경에서도 앱이 죽지 않고
정상적으로 시연 가능하도록 최적화해줘.
```

**AI 답변 요약:**
- 환경변수(`os.environ.get`)로 API 키를 조회하되, 없으면 즉시 Fallback 데이터를 반환하도록 하여
  발표/시연 환경에서 네트워크 유무와 무관하게 항상 동작하도록 보장.
- `pandas.DataFrame` 생성 시 실시간 데이터와 Fallback 데이터의 컬럼 구조를 동일하게 맞춰
  하위 로직(최저가 탐색, 지도 시각화)이 분기 없이 재사용되도록 리팩토링.

---

## 종합 소감
GitHub Copilot과의 반복적인 CoT 프롬프트를 통해 "공공 API 연동 + 즉각적인 로컬 Fallback"이라는
서비스 신뢰성의 핵심 로직을 짧은 시간 안에 구현할 수 있었으며, 50대 사용자를 고려한 고대비 UI 설계도
구체적인 요구사항 전달을 통해 빠르게 완성할 수 있었다.
