import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="챗봇")

load_dotenv(Path(__file__).parent / ".env")
gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
gemini_url = "https://generativelanguage.googleapis.com/v1beta/interactions"
gemini_model = "gemini-3.8-flash"
spare_model = "gemini-3.5-flash-lite"


def ask_gemini(text):
    # 첫 모델이 바쁘거나(503) 30초 안에 답이 없을 때만 다음 모델로 한 번 더 묻는다
    for model, wait in [(gemini_model, 30), (spare_model, 60)]:
        try:
            res = requests.post(
                gemini_url,
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={"model": model, "input": text},
                timeout=wait,
            )
        except requests.Timeout:
            if model == spare_model:
                raise
            continue
        if res.status_code != 503:
            break
    if not res.ok:
        return None, f"Gemini 가 답하지 못했습니다 ({res.status_code}) : {res.text[:300]}"
    data = res.json()
    texts = [
        block.get("text", "")
        for step in data.get("steps", [])
        if step.get("type") == "model_output"
        for block in step.get("content", [])
        if block.get("type") == "text"
    ]
    if not texts:
        return None, "Gemini 답에 글이 없습니다"
    return "".join(texts), ""


st.title("챗봇")

if gemini_key:
    st.text("GEMINI_API_KEY 가 채워져 있습니다")
else:
    st.text("GEMINI_API_KEY 가 비어 있습니다. .env 파일에 값을 넣어 주세요")
    st.stop()

question = st.text_input("물어볼 말")

if st.button("보내기"):
    if not question.strip():
        st.error("물어볼 말을 넣어 주세요")
    else:
        with st.spinner("Gemini 가 답을 쓰는 중입니다"):
            try:
                answer, error = ask_gemini(question.strip())
            except requests.RequestException as e:
                answer, error = None, f"Gemini 에 닿지 못했습니다 : {e}"
        if error:
            st.error(error)
        else:
            st.write(answer)
