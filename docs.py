import base64
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st

from read_key import read_key

st.set_page_config(page_title="문서 보관함")

url = read_key("SUPABASE_URL").rstrip("/")
key = read_key("SUPABASE_KEY")

st.title("문서 보관함")

if not url or not key:
    st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
    st.stop()

bucket = "docs"
link_seconds = 60  # 내려받기 링크가 열려 있는 시간(초)
storage_url = f"{url}/storage/v1/object"
headers = {"apikey": key, "Authorization": f"Bearer {key}"}


def to_key(original):
    # Storage 는 한글 파일 이름을 받지 않아서, 원래 이름을 영문·숫자 글자로 바꿔 이름 안에 넣는다
    encoded = base64.urlsafe_b64encode(original.encode()).decode().rstrip("=")
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    return f"{stamp}_{encoded}{Path(original).suffix.lower()}"


def to_original(name):
    # to_key 로 만든 이름에서 원래 이름을 되살린다. 되살리지 못하면 그 이름을 그대로 쓴다
    try:
        encoded = Path(name).stem.split("_", 1)[1]
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (IndexError, ValueError):
        return name


def upload(file):
    upload_headers = {**headers, "Content-Type": file.type or "application/octet-stream"}
    return requests.post(f"{storage_url}/{bucket}/{to_key(file.name)}", headers=upload_headers, data=file.getvalue(), timeout=60)


def load():
    body = {"prefix": "", "limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}}
    return requests.post(f"{storage_url}/list/{bucket}", headers=headers, json=body, timeout=10)


def sign(names):
    body = {"expiresIn": link_seconds, "paths": names}
    return requests.post(f"{storage_url}/sign/{bucket}", headers=headers, json=body, timeout=10)


def size_text(size):
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f}MB"
    return f"{max(size // 1024, 1)}KB"


with st.form("upload", clear_on_submit=True):
    files = st.file_uploader(
        "문서 고르기",
        type=["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "hwp", "hwpx", "txt", "csv", "md"],
        accept_multiple_files=True,
    )
    sent = st.form_submit_button("올리기")

try:
    if sent:
        if not files:
            st.markdown(":red[올릴 문서를 골라 주세요]")
        for file in files:
            answer = upload(file)
            if not answer.ok:
                st.text(f"{file.name} 을 올리지 못했습니다 ({answer.status_code}) : {answer.text}")

    answer = load()
    if not answer.ok:
        st.text(f"목록을 불러오지 못했습니다 ({answer.status_code}) : {answer.text}")
        st.stop()

    # 폴더(id 가 비어 있음)와 빈 폴더 표시용 파일은 빼고 문서만 남긴다
    docs = [
        item for item in answer.json()
        if item.get("id") and item["name"] != ".emptyFolderPlaceholder"
    ]
    st.caption(f"모두 {len(docs)}개 · 내려받기 링크는 {link_seconds}초 동안만 열립니다")
    if st.button("링크 새로 받기"):
        st.rerun()
    if not docs:
        st.stop()

    answer = sign([doc["name"] for doc in docs])
    if not answer.ok:
        st.text(f"내려받기 링크를 받지 못했습니다 ({answer.status_code}) : {answer.text}")
        st.stop()
    links = {item["path"]: item.get("signedURL") for item in answer.json()}

    for doc in docs:
        original = to_original(doc["name"])
        size = (doc.get("metadata") or {}).get("size") or 0
        day = (doc.get("created_at") or "")[:10]
        link = links.get(doc["name"])
        if link:
            # 원래 이름으로 내려받아지도록 download 에 원래 이름을 붙인다
            st.markdown(f"[{original}]({url}/storage/v1{link}&download={quote(original)})  ·  {day}  ·  {size_text(size)}")
        else:
            st.text(f"{original}  ·  {day}  ·  링크를 받지 못했습니다")
except requests.RequestException as error:
    st.text(f"Supabase 에 닿지 못했습니다 : {error}")
