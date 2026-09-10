REGISTRY     := myregistry.com
BACKEND_IMG  := $(REGISTRY)/qa-backend:latest
FRONTEND_IMG := $(REGISTRY)/qa-frontend:latest

.PHONY: init db up down purge

## 최초 1회 - namespace, Secret, PV/PVC(모델+DB) 생성. 이미 있으면 그대로 둠
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
	cp -r ~/url-qa-app/models/koelectra-small-qa /nfsvol/url-qa-models/

	kubectl apply -f k8s/nfs-pv-qa.yaml
	kubectl apply --server-side -f k8s/db-secret.yaml
	kubectl apply -f k8s/db-pv.yaml

## DB가 실제로 연결 가능한 상태(readinessProbe 통과)가 될 때까지 대기
## backend가 DB보다 먼저 뜨는 걸 막기 위한 선행 조건
db:
	kubectl apply -f k8s/db-deploy.yaml
	kubectl rollout status deployment/db -n qa-backend --timeout=120s

## 반복 - 빌드/push/배포. init이 만든 것에 연결만 함. db가 준비된 후에만 진행
up: db
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
	kubectl delete deployment db backend -n qa-backend
	kubectl delete service    db backend -n qa-backend
	kubectl delete deployment frontend -n qa-frontend
	kubectl delete service    frontend -n qa-frontend

## 완전 초기화 - 이 프로젝트 관련 namespace/PV/NFS 데이터까지 전부 삭제
## 이름을 정확히 지정해서 다른 네임스페이스/PV/데이터는 절대 안 건드림
purge:
	kubectl delete namespace qa-backend qa-frontend
	kubectl delete pv qa-model-pv qa-db-pv
	rm -rf /nfsvol/url-qa-models/* /nfsvol/qa-db-data/*
