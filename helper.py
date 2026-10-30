import anthropic
import streamlit as st

from read_key import read_key

st.set_page_config(page_title="챗봇")

claude_key = read_key("ANTHROPIC_API_KEY")
claude_model = "claude-opus-5-5"


def ask_claude(text):
    # 바쁘거나(429·5xx) 늦을 때는 도구가 알아서 두 번 더 묻는다
    client = anthropic.Anthropic(api_key=claude_key, timeout=60)
    try:
        # 안전 점검에 걸려 답을 못 하면 다른 모델이 이어서 답하게 한다(fallbacks)
        res = client.beta.messages.create(
            model=claude_model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.APIStatusError as e:
        return None, f"클로드가 답하지 못했습니다 ({e.status_code}) : {e.message[:300]}"
    except anthropic.APIConnectionError as e:
        return None, f"클로드에 닿지 못했습니다 : {e}"
    answer = "".join(block.text for block in res.content if block.type == "text")
    if not answer:
        return None, "클로드 답에 글이 없습니다"
    return answer, ""


st.title("챗봇")

if claude_key:
    st.text("ANTHROPIC_API_KEY 가 채워져 있습니다")
else:
    st.text("ANTHROPIC_API_KEY 가 비어 있습니다. .env 파일에 값을 넣어 주세요")
    st.stop()

question = st.text_input("물어볼 말")

if st.button("보내기"):
    if not question.strip():
        st.error("물어볼 말을 넣어 주세요")
    else:
        with st.spinner("클로드가 답을 쓰는 중입니다"):
            answer, error = ask_claude(question.strip())
        if error:
            st.error(error)
        else:
            st.write(answer)
