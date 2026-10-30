import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


# 내 컴퓨터에서는 .env 에서, 올린 곳에서는 Secrets 에서 같은 이름으로 읽는다
def read_key(name):
    value = os.getenv(name)
    if value:
        return value.strip()
    try:
        return str(st.secrets.get(name) or "").strip()
    # 내 컴퓨터에 Secrets 파일이 없을 때 나는 오류. 화면은 그대로 뜨게 빈 값을 돌려준다
    except FileNotFoundError:
        return ""
