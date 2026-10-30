from datetime import date

import requests
import streamlit as st

from read_key import read_key

st.set_page_config(page_title="구독 정리함")

url = read_key("SUPABASE_URL").rstrip("/")
key = read_key("SUPABASE_KEY")

st.title("구독 정리함")

if not url or not key:
    st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
    st.stop()

table_url = f"{url}/rest/v1/subscriptions"
headers = {"apikey": key, "Authorization": f"Bearer {key}"}


def load():
    params = {"select": "id,name,category,monthly_fee,last_used", "order": "id.asc"}
    return requests.get(table_url, headers=headers, params=params, timeout=10)


def add(row):
    return requests.post(table_url, headers=headers, json=row, timeout=10)


def change(row_id, row):
    params = {"id": f"eq.{row_id}"}
    return requests.patch(table_url, headers=headers, params=params, json=row, timeout=10)


def remove(row_id):
    params = {"id": f"eq.{row_id}"}
    return requests.delete(table_url, headers=headers, params=params, timeout=10)


def to_row(name, category, monthly_fee, last_used):
    return {
        "name": name.strip(),
        "category": category.strip(),
        "monthly_fee": int(monthly_fee),
        "last_used": last_used.isoformat() if last_used else None,
    }


def done(answer, what):
    # 잘 되면 화면을 새로 그려 바뀐 표를 보여 주고, 안 되면 까닭을 남긴다
    if answer.ok:
        st.rerun()
    st.text(f"{what} 못했습니다 ({answer.status_code}) : {answer.text}")


try:
    answer = load()
    if not answer.ok:
        st.text(f"표를 불러오지 못했습니다 ({answer.status_code}) : {answer.text}")
        st.stop()
    rows = answer.json()

    # 1. 표 보여 주기
    total = sum(row["monthly_fee"] for row in rows)
    st.caption(f"모두 {len(rows)}개 · 한 달 {total:,}원")
    st.dataframe(
        [
            {
                "번호": row["id"],
                "이름": row["name"],
                "갈래": row["category"],
                "한 달 요금(원)": row["monthly_fee"],
                "마지막으로 쓴 날": row["last_used"] or "",
            }
            for row in rows
        ],
        hide_index=True,
        use_container_width=True,
    )

    # 2. 줄 더하기
    st.subheader("줄 더하기")
    with st.form("add", clear_on_submit=True):
        name = st.text_input("이름")
        category = st.text_input("갈래")
        monthly_fee = st.number_input("한 달 요금(원)", min_value=0, step=100)
        last_used = st.date_input("마지막으로 쓴 날", value=None)
        sent = st.form_submit_button("더하기")

    if sent:
        if not name.strip() or not category.strip():
            st.markdown(":red[이름과 갈래를 넣어 주세요]")
        else:
            done(add(to_row(name, category, monthly_fee, last_used)), "줄을 더하지")

    # 3. 줄 고치기 · 지우기
    st.subheader("줄 고치기 · 지우기")
    if not rows:
        st.text("아직 줄이 없습니다")
        st.stop()

    picked = st.selectbox(
        "고칠 줄",
        rows,
        format_func=lambda row: f"{row['id']}. {row['name']}",
    )
    row_id = picked["id"]
    old_date = date.fromisoformat(picked["last_used"]) if picked["last_used"] else None

    # 칸 이름에 번호를 넣어, 다른 줄을 고르면 그 줄 값으로 칸이 새로 채워지게 한다
    with st.form(f"edit_{row_id}"):
        new_name = st.text_input("이름", value=picked["name"])
        new_category = st.text_input("갈래", value=picked["category"])
        new_fee = st.number_input("한 달 요금(원)", min_value=0, step=100, value=picked["monthly_fee"])
        new_date = st.date_input("마지막으로 쓴 날", value=old_date)
        left, right = st.columns(2)
        save = left.form_submit_button("고치기")
        delete = right.form_submit_button("지우기")

    if save:
        if not new_name.strip() or not new_category.strip():
            st.markdown(":red[이름과 갈래를 넣어 주세요]")
        else:
            done(change(row_id, to_row(new_name, new_category, new_fee, new_date)), "줄을 고치지")
    if delete:
        done(remove(row_id), "줄을 지우지")
except requests.RequestException as error:
    st.text(f"Supabase 에 닿지 못했습니다 : {error}")
