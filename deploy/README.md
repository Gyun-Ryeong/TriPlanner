# TriPlanner 배포 (AWS 학교 계정)

```
사용자 ─http:80─▶ EC2 t3.small  (Docker Compose)
                   ├─ web     : Nginx + React 빌드   ( / 화면, /api → backend )
                   ├─ backend : Spring Boot          ─┐
                   └─ rag     : FastAPI 챗봇 서버    ─┼─▶ RDS MySQL (프리티어): 회원·여행·장소 벡터
                                       └─▶ 학교 LLM 게이트웨이 (Amazon Bedrock)
```

| 파일 | 하는 일 |
| --- | --- |
| `docker-compose.yml` | 컨테이너 3개(web, backend, rag) 실행. 밖으로는 80번만 연다 |
| `nginx.conf` | `/` 는 화면, `/api/` 는 백엔드로. AI 일정 대기 15분 |
| `.env.example` | 서버 설정 예시 → `.env` 로 복사해서 값 채우기 (깃에 안 올라감) |
| `make_mysql_dump.py` | 로컬 MariaDB → RDS MySQL용 덤프 (`triplanner_mysql.sql`, 깃에 안 올라감) |
| `../frontend/Dockerfile`, `../backend/Dockerfile`, `../rag_project/Dockerfile` | 각 서버 이미지 |

배포에서 달라지는 점
- **AI**: `LLM_PROVIDER=gateway` → Ollama 대신 학교 게이트웨이(OpenAI 호환 `/chat/completions`)를 부른다. 로컬 개발은 그대로 Ollama.
- **DB**: RDS MySQL. 장소 벡터는 MySQL에서 `varbinary(1536)`로 저장하고 검색은 코드(numpy)가 하므로 MariaDB의 VECTOR 타입이 없어도 된다.
- **백엔드**: `SPRING_PROFILES_ACTIVE=prod` → `application-prod.yml` (MySQL 드라이버, 비밀 값은 환경변수).
- **챗봇 서버 패키지**: `requirements-deploy.txt` (chromadb·PyTorch·Streamlit 제외).

---

## 1. 내 PC에서 준비

1. MySQL용 덤프 만들기 (장소 47,703곳 포함, 약 185MB)
   ```
   python deploy\make_mysql_dump.py
   ```
2. 챗봇 캐시 2개를 서버로 보낼 준비: `rag_project\cache\overview_cache.json`, `rag_project\cache\category_codes.json`
   (없으면 장소 문장이 DB와 달라져 요청마다 벡터를 다시 계산해 느려진다. 분류 코드표는 서버가 켜질 때 자동으로 받지만 소개글은 복사해야 한다)

## 2. AWS 콘솔 (서울 리전)

1. **RDS**: MySQL, 템플릿 프리티어, EC2 연결 안 함, 퍼블릭 액세스 허용
   - DB 이름 `triplanner`, 마스터 비밀번호는 강하게
   - 보안 그룹 인바운드 3306: **EC2의 보안 그룹과 내 IP만** (Anywhere 금지)
2. **EC2**: Ubuntu 24.04, t3.small(학교 계정 최대), 스토리지 30GB
   - 인스턴스 프로필: `SafeInstanceProfile-triplanner-N` (생성 후 작업 → 보안 → IAM 역할 수정)
   - 보안 그룹 인바운드: 22(Anywhere-IPv4, 학교 안내), 80(Anywhere-IPv4). 보안 그룹은 태그가 자동으로 붙은 뒤에 규칙 편집 가능
   - 탄력적 IP를 할당해서 연결 (주소가 바뀌지 않게)

## 3. EC2 서버에서

```bash
# Docker 설치
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git mysql-client
sudo usermod -aG docker $USER && newgrp docker

# 메모리 2GB라 빌드·실행 때 모자라지 않게 스왑 4GB
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 코드 받기
git clone https://github.com/Gyun-Ryeong/TriPlanner.git && cd TriPlanner/deploy
cp .env.example .env && nano .env        # 값 채우기
```

내 PC에서 덤프·캐시 올리기 (PowerShell):
```
scp -i 키.pem deploy\triplanner_mysql.sql ubuntu@서버주소:~/
scp -i 키.pem rag_project\cache\overview_cache.json rag_project\cache\category_codes.json ubuntu@서버주소:~/
```

서버에서 DB 넣기 + 실행:
```bash
mysql -h RDS엔드포인트 -u admin -p -e "CREATE DATABASE IF NOT EXISTS triplanner CHARACTER SET utf8mb4"
mysql -h RDS엔드포인트 -u admin -p triplanner < ~/triplanner_mysql.sql

docker compose build rag && docker compose build backend && docker compose build web   # 메모리 2GB라 하나씩. 처음엔 20분 안팎
docker compose up -d
docker compose cp ~/overview_cache.json rag:/app/cache/
docker compose cp ~/category_codes.json rag:/app/cache/
docker compose restart rag
```

## 4. 확인

```bash
docker compose ps                        # 3개 모두 Up
docker compose logs -f backend           # 'Started BackendApplication' 이 보이면 OK
curl http://localhost/api/chat/x/progress   # 401 이면 백엔드까지 연결된 것 (로그인 필요)
```
브라우저에서 `http://탄력적IP` → 로그인 → 챗봇으로 일정 하나 만들어 보기

## 5. 외부 서비스에 주소 등록

- 네이버 클라우드 Maps: 'Web 서비스 URL'에 `http://탄력적IP` 추가 (안 하면 지도가 안 뜸)
- 네이버 로그인: 콜백 URL `http://탄력적IP/api/auth/naver/callback`
- 재난안전데이터 공유플랫폼(safetydata.go.kr): 연합뉴스 API 인증키에 **탄력적 IP 등록** (등록 안 하면 "등록되지 않은 IP"로 막히고 네이버 뉴스만 쓴다)

## 운영 팁

- 안 쓸 때: EC2 중지 (RDS는 프리티어 한도 안에서 켜 둬도 됨). 다시 켜면 컨테이너는 자동으로 뜬다 (`restart: unless-stopped`).
- 코드 바꾼 뒤: `git pull && docker compose up -d --build`
- 로그: `docker compose logs -f rag` / `backend` / `web`
- 대화 기억은 챗봇 서버 메모리에 있어서 rag 를 재시작하면 이어지던 대화 조건이 사라진다.
