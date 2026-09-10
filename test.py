# test_url_qa.py
import requests
from bs4 import BeautifulSoup
from transformers import pipeline

qa = pipeline(
    "question-answering",
    model="./models/koelectra-small-qa",
    tokenizer="./models/koelectra-small-qa"
)

def get_page_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}  # 일부 사이트는 User-Agent 없으면 차단함
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # 본문 방해되는 태그 제거 (광고, 스크립트, 네비게이션 등)
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    return text

url = "https://ko.wikipedia.org/wiki/쿠버네티스"
question = "쿠버네티스는 누가 개발했어?"

raw_text = get_page_text(url)
print(f"크롤링된 본문 길이: {len(raw_text)}자")
print(f"본문 앞부분 미리보기: {raw_text[:200]}...\n")

# 모델의 max_seq_length가 512라 너무 긴 본문은 잘라서 테스트
context = raw_text[:1500]

result = qa(question=question, context=context)
print("=== 결과 ===")
print(f"질문: {question}")
print(f"답변: {result['answer']}")
print(f"신뢰도: {result['score']:.4f}")
