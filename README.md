# TriPlanner

국내 여행의 모든 순간을 더 안전하고 자유롭게 — 맞춤 일정, 실시간 여행 알림, AI 여행 챗봇을 제공하는 국내 여행 플래너 서비스입니다.

## 팀원

- 이동희
- 김령균
- 이시우

## 주요 기능 (기획 기준)

- **여행 일정 관리**: 지역 선택 후 동선/일정 생성 및 수정
- **AI 여행 챗봇**: 최신 여행 정보 기반으로 일정·맛집 등을 추천 (RAG 기반)
- **실시간 여행 알림**: 여행지 날씨, 위험/안전 신호 실시간 확인
- **내 여행 관리**: 프로필, 여행 통계, 다가오는 여행 위험도 확인

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React (Vite), React Router |
| Backend | Java 25, Spring Boot 4.1.1 (Maven, Spring Data JPA, Spring Security + JWT) |
| Database | MariaDB (HeidiSQL로 관리) |
| 형상관리 | Git / GitHub |

## 폴더 구조

```
TriPlanner/
├── frontend/       # React 프론트엔드
├── backend/        # Spring Boot 백엔드
├── 스토리보드/      # 화면 설계 목업 이미지
└── README.md
```

## 현재 진행 상태

- **프론트엔드**: 스토리보드 10개 화면을 정적 페이지로 구현 완료. 로그인/회원가입 등 인증 로직은 없고, 화면 표시용 더미 데이터만 사용 중입니다.
- **백엔드**: 프로젝트 스캐폴딩 완료 (Maven, JPA, Security+JWT 의존성 세팅). 아직 엔티티/API 미구현.
- **지도**: 여행 동선 화면의 지도는 네이버맵 API 연동 전까지 정적 placeholder로 대체되어 있습니다.

## 시작하기 (프론트엔드)

```bash
cd frontend
npm install
npm run dev
```

기본적으로 `http://localhost:5173` 에서 실행됩니다.

프로덕션 빌드:

```bash
npm run build
```

## 시작하기 (백엔드)

1. 로컬 MariaDB를 실행하고, `triplanner` 데이터베이스를 준비합니다.
2. `backend/src/main/resources/application-local.yml.example` 을 참고해서 **본인 로컬 DB 계정 정보**로 `application-local.yml`(같은 폴더, 이미 생성되어 있고 gitignore 처리됨)을 채워주세요. 이 파일은 절대 Git에 올라가지 않습니다.
3. 실행:

```bash
cd backend
./mvnw spring-boot:run
```

기본적으로 `http://localhost:8080` 에서 실행됩니다.
