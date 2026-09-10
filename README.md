##프로젝트 개요
- URL로부터 가져온 데이터 기반의 한국어 Q/A 서비스. 질문 내역 저장.

##프로젝트 간단 파이프라인
---------------------------------------------------------------------------
브라우저 → frontend(qa-frontend) → backend(qa-backend) → 모델(NFS) / DB(NFS)
---------------------------------------------------------------------------

##실행법
Makefile기반 실행
make init  : 초기 1회 실행. PV 생성, 로컬에 있는 모델 복사 등
make purge : namespace, PV(모델 용, 데이터 저장용) 전부 삭제
make up    : 이미지 Build부터 Push, 배포까지 실행. 단, DB가 붙기 전에 backend에 붙는 문제 해결을 위해 유예시간 존재
make down  : deploy와 service를 내림

##사용 모델: monologg/koelectra-small-v3-finetuned-korquad
##모델 선정 이유 
1. 짧은 시간 내, 에러나 다양한 시도를 하여도 모델의 용량이 작아, 시간이 많이 들지 않는다는 점
2. 한국어를 이용한 모델이라는 점

##프로젝트 특징
1. namespaces
-qa-frontend
-qa-backend

2. 느슨한 결합
-front/back 각각 ConfigMap으로 관리.
-NFS에 PV를 올려, 모델+데이터 저장
-Secret은 ConfigMap과 분리 관리, --server-side apply로 평문 노출 방지


##구조
'''
.
├── Makefile
├── backend
│   ├── Dockerfile
│   ├── backend.py
│   └── requirements.txt
├── frontend
│   ├── Dockerfile
│   ├── frontend.py
│   └── requirements.txt
├── k8s
│   ├── backend-configmap.yaml
│   ├── backend-deploy.yaml
│   ├── backend-svc.yaml
│   ├── configmap.yaml
│   ├── db-deploy.yaml
│   ├── db-pv.yaml
│   ├── db-secret.yaml
│   ├── frontend-configmap.yaml
│   ├── frontend-deploy.yaml
│   ├── frontend-svc.yaml
│   └── nfs-pv-qa.yaml
├── models
├── test.py                #테스트 용
└── test_model.py          #테스트 용
'''
