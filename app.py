import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

from chatbot import show_chatbot

st.set_page_config(page_title="유라의 사이트", layout="wide")

load_dotenv(Path(__file__).parent / ".env")
supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
supabase_key = (os.getenv("SUPABASE_KEY") or "").strip()
table_url = f"{supabase_url}/rest/v1/submissions"
headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}

if "screen" not in st.session_state:
    st.session_state.screen = 1
if "count" not in st.session_state:
    st.session_state.count = None
if "empty" not in st.session_state:
    st.session_state.empty = False
if "titles" not in st.session_state:
    st.session_state.titles = []
if "upload_error" not in st.session_state:
    st.session_state.upload_error = ""


def go(screen):
    st.session_state.screen = screen
    st.session_state.upload_error = ""
    if "board" in st.query_params:
        del st.query_params["board"]


GRID_TAB = "게시판 격자"
TITLE_TAB = "실습 제목 붙이기"


def switch_tab():
    # 탭을 눌러 옮겨도 버튼으로 옮긴 것과 똑같이 화면 2·3 을 바꾼다
    go(2 if st.session_state.screen_tab == GRID_TAB else 3)


def make():
    count = st.session_state.count_input
    if count is None:
        st.session_state.empty = True
    else:
        st.session_state.empty = False
        st.session_state.count = count
        st.session_state.screen = 2


def attach():
    lines = st.session_state.titles_input.splitlines()
    st.session_state.titles = [line.strip() for line in lines if line.strip()]


def open_board(number):
    st.session_state.upload_error = ""
    st.query_params["board"] = str(number)


def opened_board():
    board = st.query_params.get("board", "")
    if board.isdecimal() and int(board) >= 1:
        return int(board)
    return None


def upload(number):
    author = st.session_state.author_input.strip()
    content = st.session_state.content_input.strip()
    if not author:
        st.session_state.upload_error = "별명을 넣어 주세요"
        return
    if not content:
        st.session_state.upload_error = "글을 넣어 주세요"
        return
    row = {"practice_no": number, "author": author, "content": content}
    try:
        answer = requests.post(table_url, headers=headers, json=row, timeout=10)
    except requests.RequestException as error:
        st.session_state.upload_error = f"Supabase 에 닿지 못했습니다 : {error}"
        return
    if answer.ok:
        st.session_state.upload_error = ""
        st.session_state.content_input = ""
    else:
        st.session_state.upload_error = f"글을 쌓지 못했습니다 ({answer.status_code}) : {answer.text}"


def show_submissions(number):
    params = {
        "select": "author,content,created_at",
        "practice_no": f"eq.{number}",
        "order": "created_at.desc",
    }
    try:
        answer = requests.get(table_url, headers=headers, params=params, timeout=10)
    except requests.RequestException as error:
        st.text(f"Supabase 에 닿지 못했습니다 : {error}")
        return
    if not answer.ok:
        st.text(f"글을 불러오지 못했습니다 ({answer.status_code}) : {answer.text}")
        return
    rows = answer.json()
    st.caption(f"모두 {len(rows)}개")
    for row in rows:
        with st.container(border=True):
            st.caption(f"{row['author']} · {row['created_at'][:10]}")
            st.text(row["content"])


board = opened_board()
if board is not None:
    st.session_state.screen = 2
elif st.session_state.count is None:
    st.session_state.screen = 1

# 넣는 것(화면 1)은 옆 칸에 늘 띄워 둔다
with st.sidebar:
    count = st.number_input(
        "실습 개수", min_value=1, step=1, value=None, placeholder="예: 20", key="count_input"
    )

    if st.session_state.empty and count is None:
        st.markdown(
            '<style>[data-testid="stNumberInputContainer"] {border: 1px solid red;}</style>',
            unsafe_allow_html=True,
        )
        st.markdown(":red[실습 개수를 넣어 주세요]")

    st.button("만들기", on_click=make)

    st.text("받은 문의를 붙여 넣으면 답변 초안을 만들어 줍니다.")

if st.session_state.screen == 1:
    st.title("클래스플로우")
    st.caption("옆 칸에 실습 개수를 넣고 [만들기]를 눌러 주세요")

else:
    # 버튼으로 화면을 옮겼을 때도 그 화면의 탭이 열려 있게 맞춘다
    st.session_state.screen_tab = GRID_TAB if st.session_state.screen == 2 else TITLE_TAB
    grid_tab, title_tab = st.tabs([GRID_TAB, TITLE_TAB], key="screen_tab", on_change=switch_tab)
    titles = st.session_state.titles

    if board is not None:
        # 커진 게시판 : 왼쪽에 글 올리는 자리, 오른쪽에 올라온 글
        with grid_tab:
            left, right = st.columns(2)

            with left:
                st.title(f"실습 {board} 게시판")
                if board <= len(titles):
                    st.text(titles[board - 1])

                if not supabase_url or not supabase_key:
                    st.text(".env 파일에 SUPABASE_URL 과 SUPABASE_KEY 값을 넣어 주세요")
                else:
                    st.text_input("별명", max_chars=20, key="author_input")
                    st.text_area("글", key="content_input")
                    if st.session_state.upload_error:
                        st.markdown(f":red[{st.session_state.upload_error}]")
                    st.button("올리기", on_click=upload, args=(board,))

                if st.session_state.count is not None:
                    st.button("게시판 격자로 돌아가기", on_click=go, args=(2,))

            if supabase_url and supabase_key:
                with right:
                    show_submissions(board)

    elif st.session_state.screen == 2:
        with grid_tab:
            count = st.session_state.count

            if count == 1:
                st.title("실습 1 게시판")
            else:
                st.title(f"실습 1~{count} 게시판")

            # 화면을 옮기는 버튼은 격자 위 한 줄에 나란히 두어 내리지 않고 보이게 한다
            first, second, _ = st.columns([1, 1, 6])
            first.button("제목 넣기", on_click=go, args=(3,))
            second.button("처음 화면으로", on_click=go, args=(1,))

            for start in range(1, count + 1, 5):
                for i, col in enumerate(st.columns(5)):
                    number = start + i
                    if number > count:
                        break
                    with col.container(border=True):
                        st.button(str(number), key=f"board_{number}")
                        label = titles[number - 1] if number <= len(titles) else f"실습 {number}"
                        st.button(
                            label,
                            key=f"open_{number}",
                            type="tertiary",
                            on_click=open_board,
                            args=(number,),
                        )

            st.caption("(칸의 글자를 누르면 그 게시판이 커집니다)")

    else:
        # 실습 제목 붙이기 : 왼쪽에 제목 넣는 칸, 오른쪽에 번호·제목 목록
        with title_tab:
            st.title("실습 제목 붙이기")
            left, right = st.columns(2)

            with left:
                st.text_area(
                    "실습 제목",
                    value="\n".join(st.session_state.titles),
                    placeholder="실습 1 제목 넣기\n실습 2 제목 넣기\n실습 3 제목 넣기\n(한 줄에 하나씩 …)",
                    key="titles_input",
                )

                attach_col, back_col = st.columns(2)
                attach_col.button("제목 붙이기", on_click=attach)
                back_col.button("게시판 격자로 돌아가기", on_click=go, args=(2,))

            with right:
                pairs = list(zip(range(1, st.session_state.count + 1), st.session_state.titles))
                if pairs:
                    st.text("\n".join(f"{number} — {title}" for number, title in pairs))

show_chatbot()
