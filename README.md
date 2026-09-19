# TriPlanner

국내 여행의 모든 순간을 더 안전하고 자유롭게 — 맞춤 일정, 실시간 여행 알림, AI 여행 챗봇을 제공하는 국내 여행 플래너 서비스입니다.

## 주요 기능 (기획 기준)

- **여행 일정 관리**: 지역 선택 후 동선/일정 생성 및 수정
- **AI 여행 챗봇**: 최신 여행 정보 기반으로 일정·맛집 등을 추천 (RAG 기반)
- **실시간 여행 알림**: 여행지 날씨, 위험/안전 신호 실시간 확인
- **내 여행 관리**: 프로필, 여행 통계, 다가오는 여행 위험도 확인

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React (Vite), React Router |
| Backend | Java 25, Spring Boot *(예정)* |
| Database | MySQL (HeidiSQL로 관리) |
| 형상관리 | Git / GitHub |

## 폴더 구조

```
TriPlanner/
├── frontend/       # React 프론트엔드
├── backend/        # Spring Boot 백엔드 (예정)
├── 스토리보드/      # 화면 설계 목업 이미지
└── README.md
```

## 현재 진행 상태

- **프론트엔드**: 스토리보드 10개 화면을 정적 페이지로 구현 완료. 로그인/회원가입 등 인증 로직은 없고, 화면 표시용 더미 데이터만 사용 중입니다.
- **백엔드**: 아직 구현 전.
- **지도**: 여행 동선 화면의 지도는 카카오맵 API 연동 전까지 정적 placeholder로 대체되어 있습니다.

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
