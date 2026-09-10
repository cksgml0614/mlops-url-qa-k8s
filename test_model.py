# test_model.py
from transformers import pipeline

qa = pipeline(
    "question-answering",
    model="./models/koelectra-small-qa",
    tokenizer="./models/koelectra-small-qa"
)

# 테스트 1: 직접 만든 context
context1 = "쿠버네티스는 컨테이너화된 애플리케이션의 배포, 확장, 관리를 자동화하는 오픈소스 플랫폼이다. 구글이 처음 개발했고 현재는 CNCF에서 관리한다."
question1 = "쿠버네티스는 누가 처음 개발했어?"

result1 = qa(question=question1, context=context1)
print("=== 테스트 1 ===")
print(f"질문: {question1}")
print(f"답변: {result1['answer']}")
print(f"신뢰도: {result1['score']:.4f}")
print()

# 테스트 2: 다른 질문으로 재확인
question2 = "쿠버네티스를 관리하는 곳은?"
result2 = qa(question=question2, context=context1)
print("=== 테스트 2 ===")
print(f"질문: {question2}")
print(f"답변: {result2['answer']}")
print(f"신뢰도: {result2['score']:.4f}")
