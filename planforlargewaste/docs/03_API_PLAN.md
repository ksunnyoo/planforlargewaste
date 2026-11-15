# API 계획서 — 대형폐기물 배출 플래너

| 항목 | 내용 |
|---|---|
| 문서 버전 | v0.2 (초안, 평가·카운터 반영) |
| 작성일 | 2026-11-13 |
| 연관 문서 | 01_PRD.md, 02_SDD.md, 04_API_SPEC.md(상세 정의) |

---

## 1. 설계 원칙
1. **버전 경로**: 모든 업무 API는 `/api/v1` 아래에 둡니다. 헬스체크만 루트 `/health`.
2. **무상태 매칭, 유상태 견적**: 품목 매칭(`parse`)은 서버에 저장하지 않고, 사람이 확정한 뒤 `estimates`에서 저장합니다.
3. **금액은 서버가 계산**: 클라이언트가 보낸 금액은 신뢰하지 않고 `item_id`와 `quantity`로 다시 계산합니다.
4. **일관된 오류 형식**: `{ "error": { "code", "message", "detail" } }`.
5. **저하 모드 명시**: LLM 실패 시에도 응답하되 `degraded: true`와 사유를 반환합니다.
6. **공개 식별자**: 견적은 내부 UUID 대신 짧은 `public_id`로 노출합니다.
7. **인증 없음(MVP)**: 로그인은 로드맵이며, 대신 레이트리밋과 일일 LLM 상한으로 남용을 막습니다.

## 2. 엔드포인트 목록

| ID | 메서드 | 경로 | 설명 | 우선순위 | 관련 기능 | LLM 사용 |
|---|---|---|---|---|---|---|
| API-01 | GET | `/health` | 서버·DB·LLM 상태 확인 | Must | 운영 | 아니오 |
| API-02 | GET | `/api/v1/municipalities` | 지원 지자체 목록, 지원 수준(`procedure_supported`), 데이터 기준일 | Must | F-01, F-08 | 아니오 |
| API-03 | GET | `/api/v1/items/search` | 품목 직접 검색 | Must | F-04 | 아니오 |
| API-04 | POST | `/api/v1/estimates/parse` | 입력 텍스트를 줄·품목 후보로 분석 | Must | F-02, F-03 | 예 |
| API-05 | POST | `/api/v1/estimates` | 확정 품목으로 견적·절차 생성·저장 | Must | F-05~F-08 | 예 |
| API-06 | GET | `/api/v1/estimates/{public_id}` | 저장된 견적 조회(공유 링크) | Should | F-09, F-10 | 아니오 |
| API-07 | POST | `/api/v1/estimates/{public_id}/feedback` | 오류·개선 피드백 제출 | Should | F-11 | 아니오 |
| API-08 | POST | `/api/v1/qa` | 절차 질문 답변 | Could | F-14 | 예 |

관리·적재 작업(데이터 정제, 색인)은 API가 아니라 `scripts/` 명령행 도구로 수행합니다. 공개 API에 관리 기능을 두지 않습니다.

## 3. 화면과 API 매핑

| 화면 | 호출 API |
|---|---|
| 입력 화면 | API-02 |
| 품목 확인 화면 | API-04, API-03 |
| 결과 화면 | API-05, API-07 |
| 공유 보기 화면 | API-06, API-07 |

호출 순서:
```
API-02 → (입력) → API-04 → (사람 확정, 필요 시 API-03) → API-05 → API-06(공유 링크로 재조회) → API-07
```

## 4. 공통 규약

### 4.1 요청·응답
- 형식: JSON(UTF-8). 날짜는 ISO 8601, 기준일은 `YYYY-MM-DD`.
- 필드명: `snake_case`.
- 금액: 원 단위 정수, 필드명에 `_won` 접미사.
- 성공 시 HTTP 200(생성은 201), 본문은 데이터 객체를 직접 반환합니다.

### 4.2 오류 형식과 코드

| HTTP | code | 상황 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | 필드 누락·범위·길이 위반 |
| 400 | `ITEM_NOT_IN_MUNICIPALITY` | 선택한 품목이 해당 지자체 품목이 아님 |
| 404 | `MUNICIPALITY_NOT_FOUND` | 지원하지 않는 지자체 코드 |
| 404 | `ESTIMATE_NOT_FOUND` | 존재하지 않는 `public_id` |
| 410 | `ESTIMATE_EXPIRED` | 만료된 견적 |
| 429 | `RATE_LIMITED` | 요청 한도 초과 (`Retry-After` 헤더) |
| 503 | `DB_UNAVAILABLE` | DB 연결 불가 |
| 500 | `INTERNAL_ERROR` | 그 외 서버 오류 |

LLM 장애는 오류로 끝내지 않고 저하 모드(`degraded: true`)로 응답합니다. 단, API-08(Q&A)은 저하 모드가 없으므로 `LLM_UNAVAILABLE`(503)을 반환합니다.

### 4.3 저하 모드 규칙
| 원인 | API-04 동작 | API-05 동작 |
|---|---|---|
| LLM 전체 실패 | 규칙 기반 줄 분리 + 검색 점수 기반 후보 | 절차를 검색된 청크 원문 목록으로 반환 |
| 임베딩 실패 | trigram 검색만 사용 | 절차 검색을 키워드 검색으로 대체 |
| 일일 상한 초과 | LLM 없이 처리 | LLM 없이 처리 |

저하 시 `degraded: true`, `degraded_reason`(`llm_unavailable` / `embedding_unavailable` / `daily_limit`)을 포함합니다.

### 4.3-1 지원 수준별 동작
| 지원 수준 | API-04 | API-05 | API-08 |
|---|---|---|---|
| 수수료 + 절차 (`procedure_supported: true`) | 정상 | 절차 포함 | 정상 |
| 수수료만 (`false`) | 정상 | `procedure.status: "unsupported"`, 안내 문구만 | `answerable: false` |
| 미지원 | `MUNICIPALITY_NOT_FOUND` | `MUNICIPALITY_NOT_FOUND` | `MUNICIPALITY_NOT_FOUND` |

### 4.4 한도
| 항목 | 값(초기값, 조정 가능) |
|---|---|
| 입력 텍스트 | 1~500자 |
| 줄 수 | 최대 30 |
| 수량 | 1~99 |
| IP당 요청 | 분당 10회 (API-04, API-05, API-08) |
| 일일 전체 LLM 호출 | 환경변수 `DAILY_LLM_LIMIT` |
| 견적 보관 | 30일 |
| 요청 제한 시간 | 25초 |

### 4.5 CORS
허용 출처는 환경변수 `CORS_ORIGINS`에 지정한 프론트 도메인과 로컬 개발 주소만 허용합니다.

## 5. 구현 순서 (일정 연계)

| 일자 | API 작업 |
|---|---|
| 11/16(월) | 프로젝트 골격, API-01, API-02, API-03, 수수료 계산 모듈 |
| 11/17(화) | API-04(파싱·매칭), API-05(계산·절차 RAG) |
| 11/18(수) | API-06, API-07, 레이트리밋(DB 카운터)·저하 모드, 평가 스크립트 |
| 11/19(목) | 오류 형식 점검, 배포 환경 CORS·환경변수 확인, (여유 시) API-08 |

## 6. 테스트 계획
| 대상 | 방법 |
|---|---|
| 계산 | 단위 테스트(경계값, 다품목, 잘못된 ID) |
| API-04 | 평가셋 매칭 64문항 실행(구성 C0~C3 비교, 06_EVAL_PLAN.md), 저하 모드 강제 테스트 |
| API-05 | 인용 존재 검사, 근거 없음 시나리오 |
| 공통 | 오류 형식·상태 코드 표 기준 계약 테스트, 레이트리밋 |

## 7. 문서화
- FastAPI 자동 문서(`/docs`)를 개발 중 확인용으로 사용합니다. 배포 환경에서는 공개 여부를 환경변수로 제어합니다.
- 본 문서와 `04_API_SPEC.md`가 기준이며, 구현이 달라지면 문서를 먼저 사용자와 확인 후 갱신합니다.
