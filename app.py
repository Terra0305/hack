# -*- coding: utf-8 -*-
"""
TruckSaver AI
전남 수산물·물류 서해안선(목포 ➔ 서울) 화물차 전용 유가·경로 관제 및 야간 해무 안전 HUD

- 지도 필터링 조기 continue 스킵 버그 수정 (전체 보기 시 모든 핀 출력)
- API 페이지네이션 루프 보완으로 전국 데이터 완전 수집
- Kakao Local API 지오코딩 2차 Fallback으로 좌표 쏠림 현상 방지
- (휴게소명, 노선명) 복합 키 적용으로 상/하행 데이터 병합 차단
"""

import os
import time
import math
from datetime import datetime, timedelta

import requests
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import folium
from streamlit_folium import st_folium

# ------------------------------------------------------------------
# 기본 설정
# ------------------------------------------------------------------
st.set_page_config(
    page_title="TruckSaver AI | 전남 서해안선 물류 관제",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

OPINET_API_KEY = os.environ.get("OPINET_API_KEY", "")
STATION_API_KEY = os.environ.get("STATION_API_KEY", "6351336951")
EX_API_KEY = os.environ.get("EX_API_KEY", "6351336951")
KMA_API_KEY = os.environ.get("KMA_API_KEY", "3c608cf944eb048c65b798020d7a1e8f58cc9e9870ccb8a3be16e020e0e53597")
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "440c14cd8f2fcf66c75edf65765be704")

STATION_API_URL = "https://data.ex.co.kr/openapi/business/curStateStation"
REST_CONV_API_URL = "https://data.ex.co.kr/openapi/restinfo/restConvList"
KAKAO_LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"
KMA_NCST_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

API_REQUEST_TIMEOUT_SEC = 3.0

# 주요 거점 사전
NATIONWIDE_CITY_COORDS = {
    "목포": (34.8118, 126.3922), "서울": (37.5665, 126.9780),
    "고창": (35.4321, 126.7012), "줄포": (35.5800, 126.6900), "군산": (35.9812, 126.7345),
    "광양항": (34.9107, 127.7167), "여수산단": (34.7604, 127.6622), "순천": (34.9506, 127.4872),
    "나주": (35.0176, 126.7108), "광주": (35.1595, 126.8526), "전주": (35.8242, 127.1480),
    "서산": (36.7812, 126.4512), "당진": (36.8811, 126.6311), "화성": (37.1511, 126.8811),
}

def _parse_won_price(value):
    if not value or not str(value).strip().endswith("원"):
        return None
    return int(str(value).replace(",", "").replace("원", "").strip())

def geocode_kakao(query: str):
    if not KAKAO_REST_API_KEY:
        return None
    try:
        resp = requests.get(
            KAKAO_LOCAL_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"},
            params={"query": query, "size": 1},
            timeout=2,
        )
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
        if not docs:
            return None
        return float(docs[0]["y"]), float(docs[0]["x"])
    except Exception:
        return None

# [개선 4] 카카오 지오코딩 2차 Fallback 적용으로 좌표 쏠림 방지
def _match_jeonnam_coords(address: str, name: str = ""):
    for city, coords in NATIONWIDE_CITY_COORDS.items():
        if city in name or city in address:
            return coords
    
    if address:
        kakao_coords = geocode_kakao(address)
        if kakao_coords:
            return kakao_coords
            
    return (34.8, 126.9)

def resolve_place_coords(query: str):
    for name, coords in NATIONWIDE_CITY_COORDS.items():
        if name in query:
            return coords
    kakao_coords = geocode_kakao(query)
    return kakao_coords if kakao_coords else NATIONWIDE_CITY_COORDS["목포"]

def latlon_to_kma_grid(lat: float, lon: float):
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2 = 30.0, 60.0
    OLON, OLAT = 126.0, 38.0
    XO, YO = 43, 136
    DEGRAD = math.pi / 180.0
    re = RE / GRID
    slat1, slat2 = SLAT1 * DEGRAD, SLAT2 * DEGRAD
    olon, olat = OLON * DEGRAD, OLAT * DEGRAD
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = re * sf / math.pow(math.tan(math.pi * 0.25 + olat * 0.5), sn)
    ra = re * sf / math.pow(math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5), sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn
    return int(ra * math.sin(theta) + XO + 1.5), int(ro - ra * math.cos(theta) + YO + 1.5)

def _wind_direction_text(deg):
    dirs = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동", "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"]
    return dirs[int((deg % 360) / 22.5 + 0.5) % 16]

def _haversine_km(p1, p2):
    lat1, lon1 = p1
    lat2, lon2 = p2
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

KMA_PTY_TEXT = {"0": "맑음/구름", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기", "5": "빗방울"}
KMA_PTY_ICON = {"0": "☀️", "1": "🌧️", "2": "🌨️", "3": "❄️", "4": "🌦️", "5": "🌧️"}

FALLBACK_STATIONS = [
    {"name": "함평천지휴게소(서울)", "brand": "알뜰", "route": "서해안선", "diesel_price": 1475, "gasoline_price": 1500, "lat": 35.1012, "lon": 126.5412},
    {"name": "고창휴게소(서울방향)", "brand": "알뜰", "route": "서해안선", "diesel_price": 1485, "gasoline_price": 1510, "lat": 35.4321, "lon": 126.7012},
    {"name": "군산휴게소(서울방향)", "brand": "SK에너지", "route": "서해안선", "diesel_price": 1492, "gasoline_price": 1518, "lat": 35.9812, "lon": 126.7345},
    {"name": "서산휴게소(서울방향)", "brand": "알뜰", "route": "서해안선", "diesel_price": 1515, "gasoline_price": 1540, "lat": 36.7812, "lon": 126.4512},
    {"name": "행담도휴게소", "brand": "SK에너지", "route": "서해안선", "diesel_price": 1545, "gasoline_price": 1570, "lat": 36.9321, "lon": 126.8212},
]

FALLBACK_REST_AREAS = [
    {"name": "함평천지 휴게소(서울)", "route": "서해안선", "lat": 35.1012, "lon": 126.5412, "amenities": "샤워실, 수면실, 24시식당, 화물차쉼터"},
    {"name": "고창 휴게소(서울방향)", "route": "서해안선", "lat": 35.4321, "lon": 126.7012, "amenities": "샤워실, 수면실, 24시식당, 화물차쉼터"},
    {"name": "군산 휴게소(서울방향)", "route": "서해안선", "lat": 35.9812, "lon": 126.7345, "amenities": "샤워실, 수면실, 편의점, 세차장"},
    {"name": "서산 휴게소(서울방향)", "route": "서해안선", "lat": 36.7812, "lon": 126.4512, "amenities": "샤워실, 24시식당, ATM"},
]

FALLBACK_WEATHER = {
    "temp": 6.8, "condition": "흐림, 짙은 해무 주의", "wind": "북서풍 4.2m/s",
    "warning": "야간 서해안선(줄포-고창) 구간 짙은 해무 및 다중추돌 위험 - 시야확보 감속 권고", "icon": "🌫️",
}

# [개선 3] 주유소 API 다중 페이지 수신 루프 적용
def fetch_gas_prices():
    try:
        if not STATION_API_KEY: raise ValueError("API KEY 미설정")
        stations, page_no = [], 1
        while page_no <= 5:
            resp = requests.get(
                STATION_API_URL,
                params={"key": STATION_API_KEY, "type": "json", "numOfRows": 99, "pageNo": page_no},
                timeout=3,
            )
            resp.raise_for_status()
            rows = resp.json().get("list", [])
            if not rows: break
            for row in rows:
                diesel_price = _parse_won_price(row.get("diselPrice"))
                if diesel_price is None: continue
                addr, name = row.get("svarAddr") or "", row.get("serviceAreaName", "이름없음")
                lat, lon = _match_jeonnam_coords(addr, name)
                stations.append({
                    "name": name, "brand": row.get("oilCompany", "-"), "route": row.get("routeName", "-"),
                    "diesel_price": diesel_price, "gasoline_price": _parse_won_price(row.get("gasolinePrice")),
                    "lat": lat, "lon": lon,
                })
            page_no += 1
        return (stations, "LIVE") if stations else (FALLBACK_STATIONS, "FALLBACK")
    except Exception:
        return FALLBACK_STATIONS, "FALLBACK"

# [개선 2] 휴게소 API totalCount 기준 정확한 페이지네이션 루프
@st.cache_data(ttl=300)
def fetch_rest_areas():
    try:
        if not EX_API_KEY: raise ValueError("API KEY 미설정")
        all_rows, page_no = [], 1
        while page_no <= 10:
            resp = requests.get(
                REST_CONV_API_URL,
                params={"key": EX_API_KEY, "type": "json", "numOfRows": 99, "pageNo": page_no},
                timeout=3,
            )
            resp.raise_for_status()
            payload = resp.json()
            rows = payload.get("list", [])
            if not rows: break
            all_rows.extend(rows)
            
            total_count = payload.get("totalCount") or payload.get("count") or 0
            num_of_rows = payload.get("numOfRows", 99) or 99
            if total_count and page_no * num_of_rows >= total_count:
                break
            page_no += 1

        rest_areas = {}
        for row in all_rows:
            name, route = row.get("stdRestNm", "이름없음"), row.get("routeNm", "-")
            address = row.get("svarAddr") or ""
            coords = _match_jeonnam_coords(address, name)
            
            # [개선 5] 상/하행 분리를 위한 (이름, 노선) 복합 키 적용
            key = (name, route)
            entry = rest_areas.setdefault(
                key,
                {"name": name, "route": route, "lat": coords[0], "lon": coords[1], "amenities": set()}
            )
            ps_name = row.get("psName")
            # [개선 6] 부정형 라벨 제외 검사
            if ps_name and not any(neg in ps_name for neg in ["없음", "폐쇄", "점검"]):
                entry["amenities"].add(ps_name)

        result = []
        for entry in rest_areas.values():
            entry["amenities"] = ", ".join(sorted(entry["amenities"])) if entry["amenities"] else "정보없음"
            result.append(entry)
        return (result, "LIVE") if result else (FALLBACK_REST_AREAS, "FALLBACK")
    except Exception:
        return FALLBACK_REST_AREAS, "FALLBACK"

def fetch_weather():
    try:
        if not KMA_API_KEY: raise ValueError("API KEY 미설정")
        nx, ny = latlon_to_kma_grid(*NATIONWIDE_CITY_COORDS["목포"])
        now = datetime.now()
        base_dt = now - timedelta(hours=1) if now.minute < 45 else now
        params = {
            "serviceKey": KMA_API_KEY, "pageNo": 1, "numOfRows": 10, "dataType": "JSON",
            "base_date": base_dt.strftime("%Y%m%d"), "base_time": base_dt.strftime("%H00"), "nx": nx, "ny": ny
        }
        resp = requests.get(KMA_NCST_URL, params=params, timeout=API_REQUEST_TIMEOUT_SEC)
        obs = {item["category"]: item["obsrValue"] for item in resp.json()["response"]["body"]["items"]["item"]}
        temp, humidity, wind_speed = float(obs.get("T1H", 0)), obs.get("REH", "-"), float(obs.get("WSD", 0))
        wind_dir = _wind_direction_text(float(obs.get("VEC", 0)))
        condition = KMA_PTY_TEXT.get(obs.get("PTY", "0"), "정보 없음")
        warning = f"{condition} 미끄럼 주의" if obs.get("PTY", "0") != "0" else "서해안선 강풍/해무 주의" if wind_speed >= 7 else None
        return {
            "temp": temp, "condition": f"{condition}, 습도 {humidity}%",
            "wind": f"{wind_dir}풍 {wind_speed:.1f}m/s", "warning": warning, "icon": KMA_PTY_ICON.get(obs.get("PTY", "0"), "🌡️")
        }, "LIVE"
    except Exception:
        return FALLBACK_WEATHER, "FALLBACK"

def fetch_kakao_route(origin_query: str, destination_query: str, fallback_route):
    try:
        origin, destination = resolve_place_coords(origin_query), resolve_place_coords(destination_query)
        resp = requests.get(
            KAKAO_DIRECTIONS_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"},
            params={"origin": f"{origin[1]},{origin[0]}", "destination": f"{destination[1]},{destination[0]}"},
            timeout=3,
        )
        route = resp.json()["routes"][0]
        route_points = []
        for road in route["sections"][0]["roads"]:
            vertexes = road.get("vertexes", [])
            for i in range(0, len(vertexes) - 1, 2):
                route_points.append((vertexes[i + 1], vertexes[i]))
        summary = route.get("summary", {})
        return {
            "points": route_points, "distance_km": summary.get("distance", 0) / 1000,
            "duration_min": summary.get("duration", 0) / 60, "toll": summary.get("fare", {}).get("toll")
        }, "LIVE"
    except Exception:
        distance_km = _haversine_km(fallback_route[0], fallback_route[-1])
        return {"points": fallback_route, "distance_km": distance_km, "duration_min": distance_km / 70 * 60, "toll": None}, "FALLBACK"

def filter_by_corridor(df, start_p, end_p):
    d_direct = _haversine_km(start_p, end_p)
    filtered = []
    for _, row in df.iterrows():
        p = (row['lat'], row['lon'])
        d_via = _haversine_km(start_p, p) + _haversine_km(p, end_p)
        if d_via <= max(d_direct * 1.35, d_direct + 50):
            filtered.append(row)
    return pd.DataFrame(filtered).reset_index(drop=True) if filtered else df

# ------------------------------------------------------------------
# UI 및 레이아웃 CSS
# ------------------------------------------------------------------
st.markdown(
    """<style>
    div[data-stale="true"] { opacity: 1 !important; filter: none !important; }
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .hud-card {
        background-color: #1E293B; border: 1px solid #334155; border-radius: 12px;
        padding: 20px; margin-bottom: 12px; min-height: 160px;
        display: flex; flex-direction: column; justify-content: center;
    }
    .hud-metric { font-size: 34px; font-weight: 800; color: #10B981; }
    .hud-label { font-size: 14px; color: #94A3B8; }
    .hud-warning { color: #F59E0B; font-weight: 700; font-size: 14px; }
    section[data-testid="stSidebar"] { background-color: #020617; border-right: 1px solid #1E293B; }
    .navi-btn {
        display: inline-block; width: 100%; text-align: center; padding: 10px;
        background-color: #FEE500; color: #000 !important; font-weight: 800;
        border-radius: 8px; text-decoration: none; margin-top: 10px; font-size: 14px;
    }
    </style>""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🚛 전남 관제 운행 정보")
    driver_name = st.text_input("기사명", value="정기철")
    start_point = st.text_input("출발지 (전남 거점)", value="목포")
    end_point = st.text_input("도착지 (수도권 유통)", value="서울")
    monthly_liter = st.slider("월 평균 주유량(L)", 500, 3000, 1800, step=50)
    st.markdown("---")
    if st.button("🎙️ 음성 안내 실행"): st.session_state["play_voice"] = True

stations_data, gas_status = fetch_gas_prices()
rest_data, rest_status = fetch_rest_areas()
weather_data, weather_status = fetch_weather()

start_coords = resolve_place_coords(start_point)
end_coords = resolve_place_coords(end_point)

raw_stations_df = pd.DataFrame(stations_data)
stations_df = filter_by_corridor(raw_stations_df, start_coords, end_coords).sort_values("diesel_price", ascending=True).reset_index(drop=True)

raw_rest_df = pd.DataFrame(rest_data)
rest_df = filter_by_corridor(raw_rest_df, start_coords, end_coords)
rest_df["amenity_count"] = rest_df["amenities"].apply(lambda a: len([x for x in str(a).split(",") if x.strip() and x.strip() != "정보없음"]))

cheapest = stations_df.iloc[0] if not stations_df.empty else pd.Series({"name":"없음","diesel_price":0,"lat":34.8,"lon":126.9})
best_rest = rest_df.loc[rest_df["amenity_count"].idxmax()] if not rest_df.empty else pd.Series({"name":"없음","amenity_count":0,"amenities":"-"})
top3_df = stations_df.head(3)

route_result, route_status = fetch_kakao_route(start_point, end_point, [start_coords, (cheapest["lat"], cheapest["lon"]), end_coords])
route_points = route_result["points"]

avg_price = int(stations_df["diesel_price"].mean()) if not stations_df.empty else 1500
savings = max(0, avg_price - int(cheapest["diesel_price"])) * monthly_liter

# 헤더 & 브리핑
st.markdown("## 🔵 TruckSaver AI — 전남 수산물·물류 서해안선 관제 HUD")
st.markdown(f"<span class='hud-label'>⚓ {driver_name} 기사님 | {start_point} ➔ {end_point} 노선 관제</span>", unsafe_allow_html=True)

st.markdown("### ⛽ 노선 맞춤 AI 최저가 주유소 TOP 3")
top3_cols = st.columns(3)
for i, top_col in enumerate(top3_cols):
    with top_col:
        if i < len(top3_df):
            row = top3_df.iloc[i]
            st.markdown(f"""<div class="hud-card">
                <div class="hud-label">{"🥇🥈🥉"[i]} {row['name']}</div>
                <div class="hud-metric">{int(row['diesel_price']):,}원</div>
                <div class="hud-label">{row.get('route','-')} | {row.get('brand','-')}</div>
                <a href="https://map.kakao.com/link/to/{row['name']},{row['lat']},{row['lon']}" target="_blank" class="navi-btn">📱 카카오내비 전송</a>
                </div>""", unsafe_allow_html=True)

# 지도 영역
map_col, table_col = st.columns([2, 1])

with map_col:
    st.markdown("### 🗺️ 최적 경로 및 관제 지도")
    selected_filter = st.radio("🎯 지도 핀 원터치 필터", ["전체 보기", "🚿 샤워실 보유", "🛏️ 수면실 보유", "⛽ 최저가만 보기"], horizontal=True)

    route_lats, route_lons = [p[0] for p in route_points], [p[1] for p in route_points]
    m = folium.Map(location=[sum(route_lats)/len(route_lats), sum(route_lons)/len(route_lons)], zoom_start=8, tiles="OpenStreetMap")

    folium.Marker(route_points[0], tooltip=f"📍 출발: {start_point}", icon=folium.Icon(color="blue", icon="play", prefix="fa")).add_to(m)
    folium.Marker(route_points[-1], tooltip=f"🏁 도착: {end_point}", icon=folium.Icon(color="red", icon="flag", prefix="fa")).add_to(m)

    # [개선 1] 주유소 핀 스킵 로직 수정 (전체 보기 시 모든 주유소 표출)
    if selected_filter in ["전체 보기", "⛽ 최저가만 보기"]:
        for i, row in stations_df.iterrows():
            is_cheapest = (i == 0)
            if selected_filter == "⛽ 최저가만 보기" and not is_cheapest:
                continue

            label_prefix = "⛽ [노선 최저가]" if is_cheapest else "⛽"
            station_label = f"{label_prefix} {row['name']} ({row.get('brand','-')}) - {row['diesel_price']:,}원"
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=station_label, tooltip=station_label,
                icon=folium.Icon(color="green" if is_cheapest else "lightgray", icon="truck" if is_cheapest else "gas-pump", prefix="fa"),
            ).add_to(m)

    # [개선 1] 휴게소 핀 스킵 로직 수정 (전체 보기 시 노선상 모든 휴게소 표출)
    if selected_filter in ["전체 보기", "🚿 샤워실 보유", "🛏️ 수면실 보유"]:
        for _, row in rest_df.iterrows():
            amenities_str = str(row.get('amenities', ''))
            
            if selected_filter == "🚿 샤워실 보유":
                if "샤워" not in amenities_str: continue
                icon_name, icon_color = "bath", "blue"
            elif selected_filter == "🛏️ 수면실 보유":
                if "수면" not in amenities_str and "쉼터" not in amenities_str: continue
                icon_name, icon_color = "bed", "purple"
            else: # "전체 보기"
                is_best = (row["name"] == best_rest["name"])
                if is_best:
                    icon_name, icon_color = "star", "red"
                elif "샤워" in amenities_str and "수면" in amenities_str:
                    icon_name, icon_color = "bed", "purple"
                elif "샤워" in amenities_str:
                    icon_name, icon_color = "bath", "blue"
                else:
                    icon_name, icon_color = "info-circle", "gray"

            rest_label = f"🛏️ {row['name']} ({row.get('route', '-')}) - {amenities_str}"
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=rest_label, tooltip=rest_label,
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            ).add_to(m)

    folium.PolyLine(route_points, color="#10B981", weight=6, opacity=0.9).add_to(m)
    st_folium(m, key=f"map_{selected_filter}", width=None, height=520)

with table_col:
    st.markdown("### ⛽ 노선 내 주유소 목록")
    st.dataframe(stations_df[["name", "route", "brand", "diesel_price"]].rename(columns={"name":"주유소", "route":"노선명", "brand":"브랜드", "diesel_price":"경유가(원)"}), hide_index=True, use_container_width=True)
    st.markdown("### 🛏️ 노선 내 휴게소 안내")
    st.dataframe(rest_df[["name", "route", "amenities"]].rename(columns={"name":"휴게소", "route":"노선명", "amenities":"편의시설"}), hide_index=True, use_container_width=True)