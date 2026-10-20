import base64
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent / ".env")
gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
gemini_url = "https://generativelanguage.googleapis.com/v1beta/interactions"
gemini_model = "gemini-3.8-flash"
spare_model = "gemini-3.5-flash-lite"
prd_text = (Path(__file__).parent / "PRD.md").read_text(encoding="utf-8")

supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
supabase_key = (os.getenv("SUPABASE_KEY") or "").strip()
chat_table_url = f"{supabase_url}/rest/v1/chat_logs"
supabase_headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
korea_time = timezone(timedelta(hours=9))

# 고정 지시문은 rule.txt 에 따로 적어 두고, 여기서 읽어 PRD.md 와 이어 붙인다
rule_text = (Path(__file__).parent / "rule.txt").read_text(encoding="utf-8").strip()
rule = rule_text + "\n\n" + "=== PRD.md ===\n" + prd_text



@st.cache_data
def bot_picture():
    # bot.png 는 커서 그대로 실으면 화면이 무거워진다. 작게 줄여 한 번만 만들어 둔다
    picture = Image.open(Path(__file__).parent / "bot.png")
    # 귀 끝부터 얼굴까지 정사각형으로 잘라, 동그라미 안에 귀와 얼굴이 크게 들어가게 한다
    picture = picture.crop((290, -30, 1230, 910))
    picture.thumbnail((160, 160))
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    return buffer.getvalue()


def copy_button(text):
    # 누르면 답 글을 통째로 복사하는 작은 버튼
    words = json.dumps(text).replace("</", "<\\/")
    components.html(
        f"""
        <button id="copy" style="font-size:13px; padding:3px 10px; border-radius:8px;
            border:1px solid #ff9db8; background:#fff5f8; cursor:pointer;">복사하기</button>
        <script>
        const words = {words};
        const button = document.getElementById("copy");
        button.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText(words);
            }} catch (e) {{
                const box = document.createElement("textarea");
                box.value = words;
                document.body.appendChild(box);
                box.select();
                document.execCommand("copy");
                box.remove();
            }}
            button.textContent = "복사했어요";
            setTimeout(() => button.textContent = "복사하기", 1500);
        }};
        </script>
        """,
        height=36,
    )


def show_message(role, text):
    # 답(assistant)에만 복사 버튼을 붙이고, 알림(notice)에는 붙이지 않는다
    if role == "user":
        with st.chat_message("user"):
            st.write(text)
        return
    with st.chat_message("assistant", avatar=bot_picture()):
        # 줄바꿈 하나도 화면에서 그대로 줄이 바뀌어 보이게 한다
        st.markdown(text.replace("\n", "  \n"))
        if role == "assistant":
            copy_button(text)


def ask_gemini(text):
    # 첫 모델이 바쁘거나(503) 30초 안에 답이 없을 때만 다음 모델로 한 번 더 묻는다
    body = {"input": text, "system_instruction": rule}
    if st.session_state.chat_last_id:
        body["previous_interaction_id"] = st.session_state.chat_last_id
    for model, wait in [(gemini_model, 30), (spare_model, 60)]:
        try:
            res = requests.post(
                gemini_url,
                headers={"x-goog-api-key": gemini_key, "Content-Type": "application/json"},
                json={**body, "model": model},
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
    st.session_state.chat_last_id = data.get("id")
    return "".join(texts), ""


def save_chat(question, answer):
    # 물은 말과 받은 답을 Supabase 의 chat_logs 표에 한 줄로 남긴다. 못 남기면 그 까닭을 돌려준다
    if not supabase_url or not supabase_key:
        return ".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값이 없어 대화를 남기지 못했습니다"
    row = {"question": question, "answer": answer}
    try:
        res = requests.post(chat_table_url, headers=supabase_headers, json=row, timeout=10)
    except requests.RequestException as e:
        return f"Supabase 에 닿지 못해 대화를 남기지 못했습니다 : {e}"
    if not res.ok:
        return f"대화를 남기지 못했습니다 ({res.status_code}) : {res.text[:300]}"
    load_chats.clear()
    return ""


@st.cache_data(ttl=60)
def load_chats():
    # 화면이 다시 그려질 때마다 Supabase 를 부르지 않도록 1분 동안 모아 둔다
    params = {"select": "question,answer,created_at", "order": "created_at.desc", "limit": "20"}
    try:
        res = requests.get(chat_table_url, headers=supabase_headers, params=params, timeout=10)
    except requests.RequestException as e:
        return None, f"Supabase 에 닿지 못했습니다 : {e}"
    if not res.ok:
        return None, f"지난 대화를 불러오지 못했습니다 ({res.status_code}) : {res.text[:300]}"
    return res.json(), ""


def korea_clock(created_at):
    # Supabase 는 세계 기준 시각으로 주므로 한국 시각으로 바꿔 보여 준다
    try:
        moment = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return moment.astimezone(korea_time).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return created_at[:16].replace("T", " ")


def show_past_chats():
    with st.expander("지난 대화 보기"):
        if not supabase_url or not supabase_key:
            st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
            return
        rows, error = load_chats()
        if error:
            st.text(error)
            return
        if not rows:
            st.caption("아직 남은 대화가 없습니다")
            return
        st.caption(f"최근 {len(rows)}개")
        for row in rows:
            with st.container(border=True):
                st.caption(korea_clock(row["created_at"]))
                st.markdown(f"**물은 말** : {row['question']}")
                st.markdown(row["answer"].replace("\n", "  \n"))


def send():
    question = st.session_state.chat_input_box.strip()
    if not question:
        return
    # 여기서는 질문만 담아 두고, 답은 대화창을 그릴 때 스피너와 함께 받는다
    st.session_state.chat_messages.append(("user", question))
    st.session_state.chat_waiting = question


def show_chatbot():
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_last_id" not in st.session_state:
        st.session_state.chat_last_id = None
    if "chat_waiting" not in st.session_state:
        st.session_state.chat_waiting = None

    # 화면 오른쪽 아래에 늘 떠 있게 자리를 고정한다
    st.markdown(
        """
        <style>
        .st-key-chatbot {
            position: fixed; right: 24px; bottom: 24px; z-index: 1000; width: auto;
        }
        .st-key-chatbot [data-testid="stPopoverButton"] {
            width: 72px; height: 72px; border-radius: 50%;
            background: #ffe3ec url("data:image/png;base64,PICTURE") center / cover no-repeat;
            border: 2px solid #ff9db8; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
        }
        /* 단추 위 글자와 화살표는 숨기고 그림만 보이게 한다 */
        .st-key-chatbot [data-testid="stPopoverButton"] > * { display: none; }
        [data-testid="stPopoverBody"] { width: 360px; max-height: 520px; }
        </style>
        """.replace("PICTURE", base64.b64encode(bot_picture()).decode()),
        unsafe_allow_html=True,
    )
    with st.container(key="chatbot"):
        with st.popover("챗봇"):
            st.markdown("**클래스플로우 도우미**")
            if not gemini_key:
                st.text(".env 파일에 GEMINI_API_KEY 값을 넣어 주세요")
                return
            show_message("notice", "안녕하세요! 클래스플로우에 대해 궁금한 걸 물어봐 주세요.")
            for role, text in st.session_state.chat_messages:
                show_message(role, text)
            if st.session_state.chat_waiting:
                with st.spinner("답을 쓰는 중이에요"):
                    try:
                        answer, error = ask_gemini(st.session_state.chat_waiting)
                    except requests.RequestException as e:
                        answer, error = None, f"Gemini 에 닿지 못했습니다 : {e}"
                message = ("notice", error) if error else ("assistant", answer)
                show_message(*message)
                st.session_state.chat_messages.append(message)
                # 제대로 받은 답만 남기고, "답하지 못했습니다" 같은 알림은 남기지 않는다
                if not error:
                    save_error = save_chat(st.session_state.chat_waiting, answer)
                    if save_error:
                        st.caption(f":red[{save_error}]")
                st.session_state.chat_waiting = None
            with st.form("chat_form", clear_on_submit=True, border=False):
                st.text_input("물어볼 말", key="chat_input_box", label_visibility="collapsed",
                              placeholder="물어볼 말을 넣어 주세요")
                st.form_submit_button("보내기", on_click=send)
            show_past_chats()
