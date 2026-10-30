import uuid
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

from read_key import read_key

st.set_page_config(page_title="사진 보관함")

url = read_key("SUPABASE_URL").rstrip("/")
key = read_key("SUPABASE_KEY")

st.title("사진 보관함")

if not url or not key:
    st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
    st.stop()

bucket = "photos"
storage_url = f"{url}/storage/v1/object"
headers = {"apikey": key, "Authorization": f"Bearer {key}"}


def upload(file):
    # 한글 파일 이름은 Storage 가 받지 않아서, 시각과 짧은 무작위 글자로 새 이름을 붙인다
    ext = Path(file.name).suffix.lower()
    name = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}{ext}"
    upload_headers = {**headers, "Content-Type": file.type or "application/octet-stream"}
    return requests.post(f"{storage_url}/{bucket}/{name}", headers=upload_headers, data=file.getvalue(), timeout=30)


def load():
    body = {"prefix": "", "limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}}
    return requests.post(f"{storage_url}/list/{bucket}", headers=headers, json=body, timeout=10)


with st.form("upload", clear_on_submit=True):
    files = st.file_uploader(
        "그림 고르기",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        accept_multiple_files=True,
    )
    sent = st.form_submit_button("올리기")

try:
    if sent:
        if not files:
            st.markdown(":red[올릴 그림을 골라 주세요]")
        for file in files:
            answer = upload(file)
            if not answer.ok:
                st.text(f"{file.name} 을 올리지 못했습니다 ({answer.status_code}) : {answer.text}")

    answer = load()
    if not answer.ok:
        st.text(f"목록을 불러오지 못했습니다 ({answer.status_code}) : {answer.text}")
    else:
        # 폴더(id 가 비어 있음)와 빈 폴더 표시용 파일은 빼고 그림만 남긴다
        photos = [
            item for item in answer.json()
            if item.get("id") and item["name"] != ".emptyFolderPlaceholder"
        ]
        st.caption(f"모두 {len(photos)}장")
        columns = st.columns(3)
        for index, photo in enumerate(photos):
            with columns[index % 3]:
                st.image(
                    f"{storage_url}/public/{bucket}/{photo['name']}",
                    caption=(photo.get("created_at") or "")[:10],
                    use_container_width=True,
                )
except requests.RequestException as error:
    st.text(f"Supabase 에 닿지 못했습니다 : {error}")
