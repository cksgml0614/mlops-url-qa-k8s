import os
import requests
from bs4 import BeautifulSoup
import mlflow
import mlflow.transformers

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
MODEL_URI = os.environ.get("MODEL_URI", "models:/koelectra-qa@champion")
MAX_CONTEXT_LEN = int(os.environ.get("MAX_CONTEXT_LEN", "1500"))

EVAL_SET = [
    {"url": "https://ko.wikipedia.org/wiki/쿠버네티스", "question": "쿠버네티스는 누가 개발했어?", "expected": "구글"},
    {"url": "https://ko.wikipedia.org/wiki/파이썬", "question": "파이썬은 누가 만들었어?", "expected": "귀도"},
    {"url": "https://ko.wikipedia.org/wiki/리눅스", "question": "리눅스는 누가 개발했어?", "expected": "리누스"},
]


def get_page_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def main():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    print(f"모델 로딩: {MODEL_URI}")
    qa_pipeline = mlflow.transformers.load_model(MODEL_URI)

    results = []
    with mlflow.start_run():
        mlflow.log_param("model_uri", MODEL_URI)
        mlflow.log_param("eval_set_size", len(EVAL_SET))

        correct = 0
        total_score = 0.0

        for i, item in enumerate(EVAL_SET):
            context = get_page_text(item["url"])[:MAX_CONTEXT_LEN]
            result = qa_pipeline(question=item["question"], context=context)
            is_correct = item["expected"] in result["answer"]

            correct += int(is_correct)
            total_score += result["score"]

            mlflow.log_metric("question_score", result["score"], step=i)

            results.append({
                "question": item["question"],
                "expected": item["expected"],
                "predicted": result["answer"],
                "score": result["score"],
                "correct": is_correct,
            })
            print(f"[{'O' if is_correct else 'X'}] {item['question']} → {result['answer']} (score={result['score']:.2f})")

        accuracy = correct / len(EVAL_SET)
        avg_score = total_score / len(EVAL_SET)

        mlflow.log_metric("accuracy", accuracy)
        mlflow.log_metric("avg_confidence", avg_score)
        mlflow.log_dict({"results": results}, "eval_results.json")

        print(f"\n정확도: {accuracy:.2%}, 평균 신뢰도: {avg_score:.2f}")


if __name__ == "__main__":
    main()
