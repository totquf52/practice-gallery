import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="한 줄 방명록")

load_dotenv(Path(__file__).parent / ".env")
url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
key = (os.getenv("SUPABASE_KEY") or "").strip()

st.title("한 줄 방명록")

if not url or not key:
    st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
    st.stop()

table_url = f"{url}/rest/v1/guestbook"
headers = {"apikey": key, "Authorization": f"Bearer {key}"}


def add(message):
    return requests.post(table_url, headers=headers, json={"message": message}, timeout=10)


def load():
    params = {"select": "message,created_at", "order": "created_at.desc"}
    return requests.get(table_url, headers=headers, params=params, timeout=10)


with st.form("write", clear_on_submit=True):
    message = st.text_input("한 줄 남기기", max_chars=100)
    sent = st.form_submit_button("남기기")

try:
    if sent:
        if not message.strip():
            st.markdown(":red[글을 넣어 주세요]")
        else:
            answer = add(message.strip())
            if not answer.ok:
                st.text(f"글을 쌓지 못했습니다 ({answer.status_code}) : {answer.text}")

    answer = load()
    if not answer.ok:
        st.text(f"글을 불러오지 못했습니다 ({answer.status_code}) : {answer.text}")
    else:
        rows = answer.json()
        st.caption(f"모두 {len(rows)}줄")
        for row in rows:
            st.text(f"{row['created_at'][:10]}  {row['message']}")
except requests.RequestException as error:
    st.text(f"Supabase 에 닿지 못했습니다 : {error}")
