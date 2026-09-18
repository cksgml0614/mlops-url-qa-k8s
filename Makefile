REGISTRY         := myregistry.com
BACKEND_IMG      := $(REGISTRY)/qa-backend:latest
FRONTEND_IMG     := $(REGISTRY)/qa-frontend:latest
MLFLOW_SERVER_IMG := $(REGISTRY)/mlflow-server:latest

.PHONY: init db mlflow up down purge pyenv-setup evaluate

## 최초 1회 - namespace, Secret, PV/PVC(모델+앱DB+MLflow DB+Artifact) 생성. 이미 있으면 그대로 둠
init:
	kubectl create namespace qa-backend  --dry-run=client -o yaml | kubectl apply -f -
	kubectl create namespace qa-frontend --dry-run=client -o yaml | kubectl apply -f -

	kubectl create secret docker-registry regcred \
		--docker-username=demouser --docker-password=password \
		--docker-server=$(REGISTRY) -n qa-backend \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret docker-registry regcred \
		--docker-username=demouser --docker-password=password \
		--docker-server=$(REGISTRY) -n qa-frontend \
		--dry-run=client -o yaml | kubectl apply -f -

	mkdir -p /nfsvol/url-qa-models /nfsvol/qa-db-data
	mkdir -p /root/url-qa-app/volumes/mlflow-db-data /root/url-qa-app/volumes/mlflow-artifacts
	cp -r ~/url-qa-app/models/koelectra-small-qa /nfsvol/url-qa-models/

	kubectl apply -f k8s/nfs-pv-qa.yaml
	kubectl apply --server-side -f k8s/db-secret.yaml
	kubectl apply -f k8s/db-pv.yaml

	kubectl apply --server-side -f k8s/mlflow-db-secret.yaml
	kubectl apply -f k8s/mlflow-db-configmap.yaml
	kubectl apply -f k8s/mlflow-db-pv.yaml
	kubectl apply -f k8s/mlflow-artifact-pv.yaml
	kubectl apply --server-side -f k8s/mlflow-auth-secret.yaml
	kubectl apply --server-side -f k8s/mlflow-client-secret.yaml

## 앱 DB(MySQL)가 실제로 연결 가능한 상태가 될 때까지 대기
db:
	kubectl apply -f k8s/db-deploy.yaml
	kubectl rollout status deployment/db -n qa-backend --timeout=120s

## MLflow 스택(Postgres → Tracking Server 순서로) 빌드/배포 및 준비 대기
mlflow:
	docker build -t mlflow-server ./mlflow-server
	docker tag mlflow-server $(MLFLOW_SERVER_IMG)
	docker push $(MLFLOW_SERVER_IMG)

	kubectl apply -f k8s/mlflow-db-deploy.yaml
	kubectl rollout status deployment/mlflow-db -n qa-backend --timeout=120s

	kubectl apply -f k8s/mlflow-server-configmap.yaml
	kubectl apply -f k8s/mlflow-server-deploy.yaml
	kubectl apply -f k8s/mlflow-server-svc.yaml
	kubectl rollout restart deploy/mlflow-server -n qa-backend
	kubectl rollout status deployment/mlflow-server -n qa-backend --timeout=120s

## 반복 - 빌드/push/배포. db, mlflow가 준비된 후에만 진행
up: db mlflow
	docker build -t summarizer-qa-backend ./backend
	docker build -t summarizer-qa-frontend ./frontend
	docker tag summarizer-qa-backend $(BACKEND_IMG)
	docker tag summarizer-qa-frontend $(FRONTEND_IMG)
	docker push $(BACKEND_IMG)
	docker push $(FRONTEND_IMG)

	kubectl apply -f k8s/backend-configmap.yaml
	kubectl apply -f k8s/backend-deploy.yaml
	kubectl apply -f k8s/backend-svc.yaml
	kubectl apply -f k8s/frontend-configmap.yaml
	kubectl apply -f k8s/frontend-deploy.yaml
	kubectl apply -f k8s/frontend-svc.yaml

	kubectl rollout restart deploy/backend  -n qa-backend
	kubectl rollout restart deploy/frontend -n qa-frontend
	kubectl rollout status  deploy/backend  -n qa-backend --timeout=120s
	kubectl rollout status  deploy/frontend -n qa-frontend --timeout=120s

## 반복 - 실행 중인 것만 내림. init이 만든 데이터/설정은 안 건드림
down:
	kubectl delete deployment db backend mlflow-db mlflow-server -n qa-backend
	kubectl delete service    db backend mlflow-db mlflow-server -n qa-backend
	kubectl delete deployment frontend -n qa-frontend
	kubectl delete service    frontend -n qa-frontend

## 완전 초기화 - 이 프로젝트 관련 namespace/PV/NFS 데이터까지 전부 삭제
## 이름을 정확히 지정해서 다른 네임스페이스/PV/데이터는 절대 안 건드림
purge:
	kubectl delete namespace qa-backend qa-frontend
	kubectl delete pv qa-model-pv qa-db-pv mlflow-db-pv mlflow-artifact-pv
	rm -rf /nfsvol/url-qa-models/* /nfsvol/qa-db-data/*
	rm -rf /root/url-qa-app/volumes/mlflow-db-data/* /root/url-qa-app/volumes/mlflow-artifacts/*

## backend 파드 안에 pyenv가 있으면 건너뛰고, 없으면 설치 (파드 재시작 전까지만 유효)
pyenv-setup:
	@BACKEND_POD=$$(kubectl get pod -n qa-backend -l app=backend -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -n qa-backend $$BACKEND_POD -- sh -c ' \
		if [ -d "$$HOME/.pyenv" ]; then \
			echo "=== pyenv 이미 있음, 설치 건너뜀 ==="; \
		else \
			echo "=== pyenv 없음, 설치 시작 (몇 분 걸릴 수 있음) ==="; \
			apt-get update && apt-get install -y \
				make build-essential libssl-dev zlib1g-dev \
				libbz2-dev libreadline-dev libsqlite3-dev curl \
				git libncursesw5-dev xz-utils tk-dev libxml2-dev \
				libxmlsec1-dev libffi-dev liblzma-dev; \
			curl https://pyenv.run | bash; \
		fi'

## 모델 평가 실행 - pyenv 준비(pyenv-setup) 후 MLproject를 가상환경에서 돌림
## 수동 호출 전용, up/down에는 안 끼어듦
evaluate: pyenv-setup
	@BACKEND_POD=$$(kubectl get pod -n qa-backend -l app=backend -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -n qa-backend $$BACKEND_POD -- rm -rf /tmp/mlflow-eval; \
	kubectl cp mlflow-eval qa-backend/$$BACKEND_POD:/tmp/mlflow-eval; \
	kubectl exec -it -n qa-backend $$BACKEND_POD -- sh -c ' \
		export PYENV_ROOT=$$HOME/.pyenv; \
		export PATH=$$PYENV_ROOT/bin:$$PATH; \
		cd /tmp/mlflow-eval && MLFLOW_TRACKING_URI=http://mlflow-server:5000 mlflow run . -e evaluate --experiment-name url-qa-evaluation'
