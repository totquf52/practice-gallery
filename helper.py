import os
from pathlib import Path

import openai
import streamlit as st
from dotenv import load_dotenv

st.set_page_config(page_title="챗봇")

load_dotenv(Path(__file__).parent / ".env")
gpt_key = (os.getenv("OPENAI_API_KEY") or "").strip()
gpt_model = "gpt-6-luna"


def ask_gpt(text):
    # 바쁘거나(429·5xx) 늦을 때는 도구가 알아서 두 번 더 묻는다
    client = openai.OpenAI(api_key=gpt_key, timeout=60)
    try:
        res = client.responses.create(model=gpt_model, input=text)
    except openai.APIStatusError as e:
        return None, f"GPT 가 답하지 못했습니다 ({e.status_code}) : {e.message[:300]}"
    except openai.APIConnectionError as e:
        return None, f"GPT 에 닿지 못했습니다 : {e}"
    if not res.output_text:
        return None, "GPT 답에 글이 없습니다"
    return res.output_text, ""


st.title("챗봇")

if gpt_key:
    st.text("OPENAI_API_KEY 가 채워져 있습니다")
else:
    st.text("OPENAI_API_KEY 가 비어 있습니다. .env 파일에 값을 넣어 주세요")
    st.stop()

question = st.text_input("물어볼 말")

if st.button("보내기"):
    if not question.strip():
        st.error("물어볼 말을 넣어 주세요")
    else:
        with st.spinner("GPT 가 답을 쓰는 중입니다"):
            answer, error = ask_gpt(question.strip())
        if error:
            st.error(error)
        else:
            st.write(answer)
