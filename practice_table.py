from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="문의 표")

csv_path = Path(__file__).parent / "data" / "56_practice-inquiries.csv"

st.title("문의 표")

if not csv_path.exists():
    st.text("data 폴더에 56_practice-inquiries.csv 파일이 없습니다")
else:
    inquiries = pd.read_csv(csv_path, encoding="utf-8-sig")
    inquiries = inquiries.rename(
        columns={"date": "날짜", "type": "종류", "message": "문의 내용", "status": "상태"}
    )

    st.caption(f"모두 {len(inquiries)}건")

    kinds = ["전체"] + sorted(inquiries["종류"].dropna().unique())
    kind = st.selectbox("종류", kinds)

    shown = inquiries if kind == "전체" else inquiries[inquiries["종류"] == kind]

    st.text(f"지금 보이는 줄 수 : {len(shown)}")
    st.dataframe(shown, hide_index=True, use_container_width=True)
