# backend.py
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import pymysql

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get("MODEL_PATH", "./models/koelectra-small-qa")
MAX_CONTEXT_LEN = int(os.environ.get("MAX_CONTEXT_LEN", "1500"))
EVIDENCE_WINDOW = int(os.environ.get("EVIDENCE_WINDOW", "60"))

DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_NAME = os.environ.get("DB_NAME", "qa_history")
DB_USER = os.environ.get("DB_USER", "qa_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

app = FastAPI()
qa_pipeline = None


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER,
        password=DB_PASSWORD, database=DB_NAME,
        autocommit=True, connect_timeout=5,
    )


def init_db():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS qa_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                url TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                evidence TEXT,
                score FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.close()


@app.on_event("startup")
def load_model():
    global qa_pipeline
    logger.info(f"모델 로딩 시작: {MODEL_PATH}")
    qa_pipeline = pipeline("question-answering", model=MODEL_PATH, tokenizer=MODEL_PATH)
    logger.info("모델 로딩 완료")
    try:
        init_db()
        logger.info("DB 초기화 완료")
    except Exception as e:
        logger.error(f"DB 초기화 실패: {e}")


class QARequest(BaseModel):
    url: str
    question: str


class QAResponse(BaseModel):
    answer: str
    score: float
    evidence: str


def get_page_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"URL 요청 실패: {e}")

    soup = BeautifulSoup(res.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def extract_evidence(context: str, start: int, end: int) -> str:
    win_start = max(0, start - EVIDENCE_WINDOW)
    win_end = min(len(context), end + EVIDENCE_WINDOW)
    snippet = context[win_start:win_end].strip()
    prefix = "..." if win_start > 0 else ""
    suffix = "..." if win_end < len(context) else ""
    return f"{prefix}{snippet}{suffix}"


@app.get("/health")
def health():
    if qa_pipeline is None:
        raise HTTPException(status_code=503, detail="모델 로딩 중")
    return {"status": "ok"}


@app.post("/qa", response_model=QAResponse)
def answer_question(req: QARequest):
    if qa_pipeline is None:
        raise HTTPException(status_code=503, detail="모델이 아직 준비되지 않았습니다")

    raw_text = get_page_text(req.url)
    if not raw_text:
        raise HTTPException(status_code=422, detail="페이지에서 텍스트를 추출하지 못했습니다")

    context = raw_text[:MAX_CONTEXT_LEN]
    result = qa_pipeline(question=req.question, context=context)
    evidence = extract_evidence(context, result["start"], result["end"])

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO qa_history (url, question, answer, evidence, score) VALUES (%s, %s, %s, %s, %s)",
                (req.url, req.question, result["answer"], evidence, result["score"]),
            )
        conn.close()
    except Exception as e:
        logger.error(f"히스토리 저장 실패: {e}")

    return QAResponse(answer=result["answer"], score=result["score"], evidence=evidence)


@app.get("/history")
def get_history(limit: int = 20):
    try:
        conn = get_db_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT url, question, answer, evidence, score, created_at "
                "FROM qa_history ORDER BY id DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"히스토리 조회 실패: {e}")
