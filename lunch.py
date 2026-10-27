import os
from pathlib import Path
from urllib.parse import quote

import altair as alt
import pandas as pd
import pydeck as pdk
import requests
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="남양주 맛집 대시보드", layout="wide")

load_dotenv(Path(__file__).parent / ".env")
kakao_key = (os.getenv("KAKAO_REST_API_KEY") or "").strip()
headers = {"Authorization": f"KakaoAK {kakao_key}"}
keyword_url = "https://dapi.kakao.com/v2/local/search/keyword.json"
address_url = "https://dapi.kakao.com/v2/local/search/address.json"
category_url = "https://dapi.kakao.com/v2/local/search/category.json"

if "places" not in st.session_state:
    st.session_state.places = None
if "error" not in st.session_state:
    st.session_state.error = ""
if "base" not in st.session_state:
    st.session_state.base = None


def find_center(area):
    # 지역 이름의 가운데 좌표를 얻어 거리를 함께 받는다. 못 찾으면 거리 없이 검색한다.
    res = requests.get(address_url, headers=headers, params={"query": area}, timeout=10)
    res.raise_for_status()
    docs = res.json()["documents"]
    if not docs:
        return None
    return docs[0]["x"], docs[0]["y"]


def fetch_pages(url, params, pages):
    rows = []
    for page in range(1, pages + 1):
        res = requests.get(url, headers=headers, params={**params, "page": page}, timeout=10)
        res.raise_for_status()
        data = res.json()
        rows += data["documents"]
        if data["meta"]["is_end"]:
            break
    return rows


def search(area, word, pages):
    center = find_center(area)
    params = {"query": f"{area} {word}", "category_group_code": "FD6", "size": 15}
    if center:
        params["x"], params["y"] = center
    return fetch_pages(keyword_url, params, pages)


def find_base(name):
    # 역·건물 같은 장소로 먼저 찾고, 없으면 동네 주소로 찾는다. 카카오가 돌려준 값만 쓴다.
    res = requests.get(keyword_url, headers=headers, params={"query": name, "size": 1}, timeout=10)
    res.raise_for_status()
    docs = res.json()["documents"]
    if docs:
        d = docs[0]
        return {
            "name": d["place_name"],
            "address": d["road_address_name"] or d["address_name"],
            "url": d["place_url"],
            "x": d["x"],
            "y": d["y"],
        }
    res = requests.get(address_url, headers=headers, params={"query": name}, timeout=10)
    res.raise_for_status()
    docs = res.json()["documents"]
    if docs:
        d = docs[0]
        return {"name": d["address_name"], "address": d["address_name"], "url": "", "x": d["x"], "y": d["y"]}
    return None


def search_near(base, food, radius, pages):
    params = {"category_group_code": "FD6", "x": base["x"], "y": base["y"], "radius": radius, "sort": "distance", "size": 15}
    # 찾을 음식을 비우면 그 둘레의 음식점 전체를 분류로 찾는다.
    if food:
        rows = fetch_pages(keyword_url, {**params, "query": food}, pages)
    else:
        rows = fetch_pages(category_url, params, pages)
    # 문서에 반경 밖이 빠진다는 말이 없어서, 받은 거리로 한 번 더 거른다.
    return [r for r in rows if r["distance"] and int(r["distance"]) <= radius]


def run(job):
    st.session_state.error = ""
    if not kakao_key:
        st.session_state.error = ".env 에 KAKAO_REST_API_KEY 가 없습니다."
        return
    try:
        job()
    except requests.HTTPError as e:
        st.session_state.error = f"카카오에서 오류가 왔습니다 ({e.response.status_code}) : {e.response.text}"
    except requests.RequestException as e:
        st.session_state.error = f"카카오에 닿지 못했습니다 : {e}"


def on_search():
    def job():
        st.session_state.base = None
        st.session_state.places = search(
            st.session_state.area.strip() or "남양주",
            st.session_state.word.strip() or "맛집",
            st.session_state.pages,
        )

    run(job)


def on_near():
    def job():
        name = st.session_state.base_name.strip()
        if not name:
            st.session_state.error = "기준 장소를 넣어 주세요."
            return
        base = find_base(name)
        if base is None:
            st.session_state.base = None
            st.session_state.places = None
            st.session_state.error = f"카카오에서 '{name}' 장소를 찾지 못했습니다. 이름을 바꿔 넣어 보세요."
            return
        food = st.session_state.food.strip()
        radius = st.session_state.radius
        base.update({"typed": name, "food": food or "음식점 전체", "radius": radius})
        st.session_state.base = base
        st.session_state.places = search_near(base, food, radius, st.session_state.near_pages)

    run(job)


def radius_text(m):
    return f"{m}m" if m < 1000 else f"{m / 1000:g}km"


def to_table(places):
    df = pd.DataFrame(places)
    if df.empty:
        return df
    df["분류"] = df["category_name"].str.split(" > ").str[-1]
    df["거리(m)"] = pd.to_numeric(df["distance"], errors="coerce")
    df["주소"] = df["road_address_name"].where(df["road_address_name"] != "", df["address_name"])
    df["경도"] = pd.to_numeric(df["x"])
    df["위도"] = pd.to_numeric(df["y"])
    # 가게 이름과 도로명 주소를 띄어 이어 붙여 네이버 지도 검색 주소를 만든다. 받은 값으로만 만들고 카카오는 다시 부르지 않는다.
    naver_words = (df["place_name"] + " " + df["road_address_name"]).str.strip()
    df["네이버 지도"] = "https://map.naver.com/p/search/" + naver_words.map(lambda w: quote(w, safe=""))
    df = df.rename(columns={"place_name": "이름", "phone": "전화", "place_url": "카카오맵"})
    return df[["이름", "분류", "거리(m)", "주소", "전화", "카카오맵", "네이버 지도", "경도", "위도"]]


st.title("남양주 맛집 대시보드")

# 폼 안의 값은 버튼을 누를 때만 넘어가므로, 카카오는 [검색]을 눌렀을 때만 불린다.
tab_area, tab_near = st.tabs(["지역으로 찾기", "내 조건으로 찾기"])
with tab_area:
    with st.form("search_form"):
        c1, c2, c3 = st.columns([2, 2, 1])
        c1.text_input("지역", value="남양주", key="area")
        c2.text_input("검색어", value="맛집", key="word")
        c3.number_input("가져올 쪽 수 (한 쪽에 15곳)", min_value=1, max_value=3, value=3, key="pages")
        st.form_submit_button("검색", on_click=on_search, type="primary")

with tab_near:
    with st.form("near_form"):
        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        c1.text_input("기준 장소 (역이나 동네 이름)", placeholder="예: 평내호평역, 다산동", key="base_name")
        c2.text_input("찾을 음식", placeholder="예: 국밥 (비우면 음식점 전체)", key="food")
        c3.selectbox("반경", [300, 500, 1000, 2000, 3000, 5000], index=2, format_func=radius_text, key="radius")
        c4.number_input("가져올 쪽 수 (한 쪽에 15곳)", min_value=1, max_value=3, value=3, key="near_pages")
        st.form_submit_button("검색", on_click=on_near, type="primary")

if st.session_state.error:
    st.error(st.session_state.error)

base = st.session_state.base
if base and st.session_state.places is not None:
    link = f" · [카카오맵에서 보기]({base['url']})" if base["url"] else ""
    st.info(
        f"**카카오에서 찾은 기준 장소** : {base['name']} ({base['address']}){link}  \n"
        f"넣은 이름 '{base['typed']}' 로 찾은 곳입니다. 이 둘레 {radius_text(base['radius'])} 안에서 "
        f"'{base['food']}' 을(를) 찾았습니다."
    )

if st.session_state.places is None:
    st.info("지역과 검색어를 넣고 [검색]을 눌러 주세요.")
    st.stop()

df = to_table(st.session_state.places)
if df.empty:
    st.warning("찾은 음식점이 없습니다. 검색어를 바꿔 보세요.")
    st.stop()

f1, f2, f3 = st.columns([2, 2, 1])
name_filter = f1.text_input("이름으로 거르기", placeholder="예: 국밥")
kinds = sorted(df["분류"].unique())
picked = f2.multiselect("분류 고르기", kinds, default=kinds)
sort_options = ["거리 가까운 순", "이름순", "분류순"] if df["거리(m)"].notna().any() else ["이름순", "분류순"]
sort_by = f3.selectbox("정렬", sort_options)

view = df[df["분류"].isin(picked)]
if name_filter:
    view = view[view["이름"].str.contains(name_filter, case=False, regex=False)]
if sort_by == "거리 가까운 순":
    view = view.sort_values("거리(m)")
elif sort_by == "이름순":
    view = view.sort_values("이름")
else:
    view = view.sort_values(["분류", "이름"])

m1, m2, m3 = st.columns(3)
m1.metric("찾은 음식점", f"{len(view)}곳")
m2.metric("분류 수", f"{view['분류'].nunique()}개")
near = view["거리(m)"].min()
m3.metric("가장 가까운 곳", "-" if pd.isna(near) else f"{near / 1000:.1f}km")

st.subheader("음식점 지도")
if view.empty:
    st.caption("보여 줄 음식점이 없습니다.")
else:
    # 점에 마우스를 올리면 이름·분류·주소가 뜬다.
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=view,
        get_position=["경도", "위도"],
        get_fill_color=[59, 111, 216, 200],
        get_line_color=[255, 255, 255],
        line_width_min_pixels=2,
        stroked=True,
        get_radius=60,
        radius_min_pixels=6,
        radius_max_pixels=14,
        pickable=True,
    )
    camera = pdk.ViewState(latitude=view["위도"].mean(), longitude=view["경도"].mean(), zoom=11)
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=camera,
            tooltip={"text": "{이름}\n{분류}\n{주소}"},
        ),
        use_container_width=True,
    )

left, right = st.columns([3, 2])
with left:
    st.subheader("음식점 목록")
    st.dataframe(
        view.drop(columns=["경도", "위도"]),
        hide_index=True,
        use_container_width=True,
        column_config={
            "카카오맵": st.column_config.LinkColumn("카카오맵", display_text="열기"),
            "네이버 지도": st.column_config.LinkColumn("네이버 지도", display_text="열기"),
        },
    )

with right:
    st.subheader("분류별 음식점 수")
    counts = view["분류"].value_counts().reset_index()
    counts.columns = ["분류", "곳 수"]
    if counts.empty:
        st.caption("보여 줄 음식점이 없습니다.")
    else:
        chart = (
            alt.Chart(counts)
            .mark_bar(color="#3b6fd8", cornerRadiusEnd=4, size=14)
            .encode(
                x=alt.X("곳 수:Q", title="곳 수", axis=alt.Axis(tickMinStep=1, grid=True, gridOpacity=0.3)),
                y=alt.Y("분류:N", sort="-x", title=None),
                tooltip=["분류", "곳 수"],
            )
            .properties(height=max(160, 26 * len(counts)))
        )
        st.altair_chart(chart, use_container_width=True)

st.caption(f"카카오 로컬 검색 결과 전체 {len(df)}곳 중 조건에 맞는 곳만 보여 줍니다.")
