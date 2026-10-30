from pathlib import Path

import requests
import streamlit as st

from chatbot import show_chatbot
from read_key import read_key

st.set_page_config(page_title="유라의 사이트", layout="wide")

supabase_url = read_key("SUPABASE_URL").rstrip("/")
supabase_key = read_key("SUPABASE_KEY")
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
if "landing" not in st.session_state:
    st.session_state.landing = True


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
    for index, row in enumerate(rows):
        with st.container(border=True, key=f"post_{index}"):
            st.caption(f"{row['author']} · {row['created_at'][:10]}")
            st.text(row["content"])


def start():
    st.session_state.landing = False


def to_landing():
    st.session_state.landing = True
    if "board" in st.query_params:
        del st.query_params["board"]


HERO_VIDEO = Path(__file__).parent / "static" / "hero.mp4"

LANDING_STYLE = """
<style>
@font-face {
  font-family: "Parkdahyeon";
  src: url("./app/static/ongeulip-parkdahyeon.ttf") format("truetype");
  font-display: swap;
}
[data-testid="stApp"] {
  background:
    radial-gradient(60rem 28rem at 50% -8rem, rgba(239, 85, 147, 0.28), transparent 70%),
    radial-gradient(40rem 20rem at 85% 60%, rgba(239, 85, 147, 0.08), transparent 70%),
    #150d0e;
  color: #e4cad5;
}
[data-testid="stHeader"] { background: transparent; }
.landing, .landing *, .st-key-start button, .st-key-start button * { font-family: "Parkdahyeon", sans-serif; }
.landing { text-align: center; max-width: 960px; margin: 0 auto; }
.st-key-hero {
  position: relative; isolation: isolate; overflow: hidden; justify-content: center;
  min-height: 78vh; margin-top: 2vh; padding: 6vh 24px; border-radius: 28px;
}
/* 영상은 히어로 영역을 꽉 채우고 맨 뒤에 깐다. 재생 단추는 숨기고 눌리지 않게 한다 */
.st-key-hero-video { position: absolute !important; inset: 0; z-index: 0; pointer-events: none; }
.st-key-hero-video div { width: 100% !important; height: 100% !important; }
.st-key-hero-video video { width: 100%; height: 100%; object-fit: cover; display: block; }
.st-key-hero-video video::-webkit-media-controls { display: none !important; }
/* 영상 위에 어두운 막을 한 겹 덮어 가운데 글자가 잘 보이게 한다 */
.st-key-hero-video::after {
  content: ""; position: absolute; inset: 0;
  background: radial-gradient(ellipse at center, rgba(21, 13, 14, 0.35) 0%, rgba(21, 13, 14, 0.8) 75%);
}
.st-key-hero .landing, .st-key-hero .st-key-start { position: relative; z-index: 1; }
.landing-badge {
  display: inline-block; padding: 6px 16px; border-radius: 999px;
  border: 1px solid rgba(239, 85, 147, 0.5); background: rgba(239, 85, 147, 0.1);
  color: #ef5593; font-size: 1rem; letter-spacing: 0.04em;
}
.landing h1 {
  font-size: clamp(3.2rem, 9vw, 6.4rem); line-height: 1.05; margin: 1.2rem 0 0.8rem;
  padding: 0; font-weight: 400; color: #e4cad5;
  background: linear-gradient(180deg, #ffffff 0%, #e4cad5 55%, #ef5593 140%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.landing-intro { font-size: clamp(1.15rem, 2.2vw, 1.45rem); color: #e4cad5; opacity: 0.82; margin: 0 auto 2rem !important; max-width: 720px; text-align: center !important; }
.st-key-start button {
  background: #ef5593; color: #150d0e; border: none; border-radius: 999px;
  padding: 0.7rem 2.8rem;
  box-shadow: 0 0 0 1px rgba(239, 85, 147, 0.4), 0 10px 40px rgba(239, 85, 147, 0.35);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.st-key-start button p { font-size: 1.25rem; }
.st-key-start button:hover {
  background: #ef5593; color: #150d0e; transform: translateY(-2px);
  box-shadow: 0 0 0 1px rgba(239, 85, 147, 0.6), 0 14px 50px rgba(239, 85, 147, 0.5);
}
.st-key-start button:focus:not(:active) { color: #150d0e; border: none; }
.landing-window {
  margin: 3.2rem auto 0; max-width: 820px; border-radius: 16px; overflow: hidden; text-align: left;
  border: 1px solid rgba(228, 202, 213, 0.14); background: rgba(228, 202, 213, 0.03);
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55), 0 0 60px rgba(239, 85, 147, 0.08);
}
.landing-bar {
  display: flex; align-items: center; gap: 7px; padding: 12px 16px;
  border-bottom: 1px solid rgba(228, 202, 213, 0.1); font-size: 0.95rem; color: rgba(228, 202, 213, 0.6);
}
.landing-bar i { width: 10px; height: 10px; border-radius: 50%; background: rgba(228, 202, 213, 0.18); display: inline-block; }
.landing-bar span { margin-left: 10px; }
.landing-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; padding: 18px; }
.landing-cell {
  height: 52px; border-radius: 10px; padding: 7px 10px; font-size: 0.95rem;
  border: 1px solid rgba(228, 202, 213, 0.12); background: rgba(228, 202, 213, 0.04); color: rgba(228, 202, 213, 0.75);
}
.landing-cell.on { border-color: #ef5593; background: rgba(239, 85, 147, 0.14); color: #ef5593; }
.landing-features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin: 3.6rem 0 3rem; text-align: left; }
.landing-feature {
  padding: 22px 22px 24px; border-radius: 14px;
  border: 1px solid rgba(228, 202, 213, 0.1); background: rgba(228, 202, 213, 0.03);
}
.landing-feature em { font-style: normal; color: #ef5593; font-size: 1rem; }
.landing-feature b { display: block; font-weight: 400; font-size: 1.5rem; color: #e4cad5; margin: 6px 0 8px; }
.landing-feature p { margin: 0; font-size: 1.05rem; line-height: 1.55; color: rgba(228, 202, 213, 0.72); }
.landing-foot { color: rgba(228, 202, 213, 0.45); font-size: 0.95rem; margin-bottom: 2rem; }
@media (max-width: 720px) {
  .landing-features { grid-template-columns: 1fr; }
  .landing-grid { gap: 6px; padding: 12px; }
  .landing-cell { height: 40px; font-size: 0.85rem; }
}
</style>
"""


def show_landing():
    # 색과 글꼴은 첫 화면에만 입힌다. 기능 화면은 원래 모양 그대로 둔다
    # 글 덩어리 사이에 빈 줄이나 앞쪽 띄어쓰기가 있으면 글로 찍혀 나오므로 한 줄로 이어 붙인다
    st.markdown(LANDING_STYLE, unsafe_allow_html=True)

    # 히어로 영역 : 배경 영상 위에 큰 제목 · 한 줄 소개 · 시작하기 버튼을 올린다
    with st.container(key="hero"):
        # 영상은 make_hero.py 로 만든다. 아직 없으면 영상 없이 빛 번짐 배경만 보인다
        if HERO_VIDEO.exists():
            with st.container(key="hero-video"):
                st.video(str(HERO_VIDEO), autoplay=True, muted=True, loop=True)

        # 소개 글은 PRD.md 의 한 줄 정의, 사용자, 넣을 기능에서 가져왔다
        st.markdown(
            '<div class="landing">'
            '<div class="landing-badge">혼자 과정을 진행하는 강사를 위한 도구</div>'
            "<h1>클래스플로우</h1>"
            '<div class="landing-intro">실습 개수를 넣으면 실습별 결과물 게시판이 '
            "한 화면에 격자로 한 번에 만들어지는 도구</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        # 버튼 겉상자는 버튼 크기만큼만 자리를 잡으므로, 가운데 정렬 상자에 넣어 가운데에 둔다
        with st.container(horizontal_alignment="center"):
            st.button("시작하기", key="start", on_click=start)

    # 화면 2 를 본뜬 미리보기 : 실습 20개 게시판 격자, 하나는 눌린 칸처럼 강조한다
    cells = "".join(
        f'<div class="landing-cell{" on" if number == 7 else ""}">{number}</div>'
        for number in range(1, 21)
    )
    features = [
        ("01", "한 번에 만들기", "실습 개수 하나만 넣으면 실습별 결과물 게시판이 번호 순으로 한 번에 만들어져요."),
        ("02", "한눈에 보기", "만들어진 게시판이 한 화면에 격자로 다 보이고, 칸을 누르면 그 게시판이 커져요."),
        ("03", "제목 붙이기", "실습 제목을 한 줄에 하나씩 붙여 넣으면 게시판마다 그 실습 제목이 붙어요."),
    ]
    cards = "".join(
        f'<div class="landing-feature"><em>{number}</em><b>{name}</b><p>{text}</p></div>'
        for number, name, text in features
    )
    st.markdown(
        '<div class="landing">'
        '<div class="landing-window">'
        '<div class="landing-bar"><i></i><i></i><i></i><span>실습 1~20 게시판</span></div>'
        f'<div class="landing-grid">{cells}</div>'
        "</div>"
        f'<div class="landing-features">{cards}</div>'
        '<div class="landing-foot">클래스플로우 · 실습 슬라이드를 넘길 때마다, 수업이 끝나고 결과물을 확인할 때</div>'
        "</div>",
        unsafe_allow_html=True,
    )


# 처음 열면 첫 화면이 먼저 뜬다. 복사한 게시판 링크로 들어오면 바로 그 게시판을 연다
if st.session_state.landing and opened_board() is None:
    show_landing()
    st.stop()

# 기능 화면 모양 : 테두리 없는 둥근 카드, 왼쪽 네모 번호 칸, 고른 것에만 강조 색
# 글자와 하는 일은 그대로 두고 생김새만 바꾼다
# 숫자 칸 빨간 테두리(안내 문구와 함께 뜨는 것)는 이 뒤에 그려지므로 그대로 이긴다
st.markdown(
    """
<style>
h1 { font-size: 2rem !important; letter-spacing: -0.01em; }
[data-testid="stCaptionContainer"] { color: rgba(228, 202, 213, 0.55); }
[class*="st-key-cell_"], [class*="st-key-post_"] {
  border: 1px solid transparent !important; border-radius: 16px !important;
  background: rgba(228, 202, 213, 0.05); padding: 12px 12px 10px !important; gap: 4px !important;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}
[class*="st-key-cell_"]:hover {
  border-color: rgba(239, 85, 147, 0.45) !important; background: rgba(239, 85, 147, 0.1);
  transform: translateY(-2px);
}
[class*="st-key-board_"] button {
  width: 44px; height: 44px; min-height: 44px; padding: 0; border-radius: 12px;
  border: none; background: #150d0e; color: #ef5593;
}
[class*="st-key-board_"] button p { font-weight: 700; }
[class*="st-key-board_"] button:hover { background: #ef5593; color: #150d0e; }
[class*="st-key-open_"] button p { font-size: 15px; font-weight: 600; }
[class*="st-key-open_"] button:hover p { color: #ef5593; }
[data-testid="stTabs"] [role="tablist"] {
  gap: 4px; padding: 4px; border-radius: 999px; background: rgba(228, 202, 213, 0.05); width: fit-content;
}
[data-testid="stTabs"] [role="tab"] { padding: 6px 18px; border-radius: 999px; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { background: rgba(239, 85, 147, 0.16); }
[data-testid="stTabs"] [data-baseweb="tab-highlight"], [data-testid="stTabs"] [data-baseweb="tab-border"] { display: none; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
  font-size: 13px; color: rgba(228, 202, 213, 0.55);
}
</style>
""",
    unsafe_allow_html=True,
)

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

    st.button("소개 화면으로", on_click=to_landing)

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
                    with col.container(border=True, key=f"cell_{number}"):
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
