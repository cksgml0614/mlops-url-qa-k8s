FROM python:3.11-slim

RUN pip install --no-cache-dir mlflow psycopg2-binary Flask-WTF

EXPOSE 5000

CMD ["sh", "-c", "mlflow server --host 0.0.0.0 --port 5000 \
    --app-name basic-auth \
    --backend-store-uri postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$DB_HOST:$DB_PORT/$POSTGRES_DB \
    --serve-artifacts \
    --artifacts-destination /mlartifacts"]
