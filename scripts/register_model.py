import os
import mlflow
import mlflow.transformers
from transformers import pipeline
from mlflow.client import MlflowClient

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-server:5000")
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models/koelectra-small-qa")
MODEL_NAME = "koelectra-qa"

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
mlflow.set_experiment("url-qa-experiments")

qa_pipeline = pipeline("question-answering", model=MODEL_PATH, tokenizer=MODEL_PATH)

with mlflow.start_run(run_name="register-koelectra-qa"):
    model_info = mlflow.transformers.log_model(
        transformers_model=qa_pipeline,
        artifact_path="model",
        registered_model_name=MODEL_NAME,
    )

client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
client.set_registered_model_alias(name=MODEL_NAME, alias="champion", version=model_info.registered_model_version)

print(f"등록 완료: {MODEL_NAME} v{model_info.registered_model_version} → @champion")
