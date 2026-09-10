# frontend.py
import streamlit as st
import requests
import os
import time

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


def request_with_retry(method, url, retries=3, delay=1.5, **kwargs):
    last_exc = None
    for attempt in range(retries):
        try:
            res = requests.request(method, url, **kwargs)
            res.raise_for_status()
            return res
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_exc


st.set_page_config(page_title="URL 기반 QA", page_icon="🔍")
st.title("URL 기반 질의응답")

tab1, tab2 = st.tabs(["질문하기", "질문 기록"])

with tab1:
    url = st.text_input("URL을 입력하세요", placeholder="https://ko.wikipedia.org/wiki/쿠버네티스")
    question = st.text_input("질문을 입력하세요", placeholder="쿠버네티스는 누가 개발했어?")

    if st.button("질문하기"):
        if not url or not question:
            st.warning("URL과 질문을 모두 입력해주세요.")
        else:
            with st.spinner("답변을 찾는 중..."):
                try:
                    res = request_with_retry(
                        "POST", f"{BACKEND_BASE_URL}/qa",
                        json={"url": url, "question": question},
                        timeout=30
                    )
                    data = res.json()
                    st.success(f"**답변:** {data['answer']}")
                    st.caption(f"신뢰도: {data['score']:.2f}")
                    st.markdown(f"**근거:** _{data['evidence']}_")
                except requests.exceptions.RequestException as e:
                    st.error(f"요청 실패: {e}")

with tab2:
    if st.button("기록 새로고침"):
        st.rerun()
    try:
        res = request_with_retry("GET", f"{BACKEND_BASE_URL}/history", timeout=10)
        for item in res.json():
            with st.expander(f"{item['question']}  ({item['created_at']})"):
                st.write(f"URL: {item['url']}")
                st.write(f"답변: {item['answer']}")
                st.write(f"근거: {item['evidence']}")
                st.write(f"신뢰도: {item['score']:.2f}")
    except requests.exceptions.RequestException as e:
        st.error(f"기록 조회 실패: {e}")
