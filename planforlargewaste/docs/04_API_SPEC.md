# API 정의서 — 대형폐기물 배출 플래너

| 항목 | 내용 |
|---|---|
| 문서 버전 | v0.2 (초안, fee_type, spec_missing 반영) |
| 작성일 | 2026-11-13 |
| Base URL | 로컬 `http://127.0.0.1:8000`, 배포 `https://<백엔드-도메인>` |
| 업무 API 접두사 | `/api/v1` |
| 형식 | JSON(UTF-8), 필드명 snake_case, 금액은 원 단위 정수(`_won`) |
| 인증 | 없음(MVP) |

> 예시의 품목명·금액·지자체 코드는 형식을 보여주는 **가상 값**입니다. 실제 값은 적재된 공공데이터를 따릅니다.

---

## 0. 공통 객체

### Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력 내용을 확인하십시오.",
    "detail": [{ "field": "text", "reason": "최대 500자까지 입력할 수 있습니다." }]
  }
}
```
오류 코드와 HTTP 상태는 API 계획서 4.2절 표를 따릅니다.

### Meta (견적·분석 응답 공통)
| 필드 | 타입 | 설명 |
|---|---|---|
| `degraded` | boolean | 저하 모드 여부 |
| `degraded_reason` | string \| null | `llm_unavailable`, `embedding_unavailable`, `daily_limit` |
| `data_base_date` | string(date) | 사용한 수수료 데이터의 기준일 |
| `disclaimer` | string | 면책 문구 |

---

## API-01 헬스체크

`GET /health`

**200 응답**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "ok",
  "llm": { "primary": "available", "fallback": "available" }
}
```
| 필드 | 값 |
|---|---|
| `status` | `ok` / `degraded` |
| `db` | `ok` / `down` |
| `llm.*` | `available` / `unavailable` / `unknown` |

DB가 내려가 있어도 HTTP 200으로 `status: "degraded"`, `db: "down"`을 반환합니다(유지 호출이 실패로 중단되지 않도록).

---

## API-02 지원 지자체 목록

`GET /api/v1/municipalities`

**200 응답**
```json
{
  "items": [
    {
      "code": "3780000",
      "name": "경기도 성남시",
      "support_level": "fee_and_procedure",
      "procedure_supported": true,
      "spec_missing": false,
      "data_base_date": "2026-11-13",
      "legal_effective_date": "2026-10-26",
      "item_count": 0
    },
    {
      "code": "0000000",
      "name": "예시 지자체(수수료만 제공)",
      "support_level": "fee_only",
      "procedure_supported": false,
      "spec_missing": true,
      "data_base_date": "2026-11-01",
      "item_count": 0
    }
  ]
}
```
- `code`: 행정기관코드 7자리(전국 데이터의 제공기관코드와 동일, 예: 수원시 3740000). 성남시 3780000은 코드 체계 추정값이라 **[검증 필요]**, 예시 `0000000`은 가상 값.
- `support_level`: `fee_and_procedure`(수수료+절차) 또는 `fee_only`(수수료만). 수수료 데이터가 없는 지자체는 목록에 포함하지 않습니다(미지원).
- `procedure_supported`: 절차 안내 제공 여부.
- `spec_missing`: 규격이 전부 빈칸인 지자체이면 `true`. 화면은 "이 지자체는 규격 정보가 제공되지 않습니다. 수수료는 참고용이며 해당 지자체에 확인하십시오." 경고를 표시합니다.
- `data_base_date`: 데이터 기준일(성남시는 확인일), `legal_effective_date`: 근거 규정 시행일(알 수 있는 경우만).
- `item_count`: 적재된 품목 수.

---

## API-03 품목 직접 검색

`GET /api/v1/items/search`

**쿼리 파라미터**
| 이름 | 필수 | 타입 | 설명 |
|---|---|---|---|
| `municipality_code` | 예 | string | 지자체 코드 |
| `q` | 예 | string | 검색어(1~50자) |
| `limit` | 아니오 | int | 기본 10, 최대 20 |

**200 응답**
```json
{
  "items": [
    {
      "item_id": 101,
      "category": "가구류",
      "name": "소파",
      "spec": "3인용",
      "fee_won": 10000,
      "fee_type": "paid",
      "score": 0.82
    }
  ]
}
```
- 검색은 trigram 유사도 기반이며 LLM을 사용하지 않습니다.
- 오류: `VALIDATION_ERROR`, `MUNICIPALITY_NOT_FOUND`.

---

## API-04 입력 분석·품목 후보

`POST /api/v1/estimates/parse`

서버에 저장하지 않습니다.

**요청**
```json
{
  "municipality_code": "3780000",
  "text": "3인용 소파, 책상, 의자 4개"
}
```
| 필드 | 필수 | 제약 |
|---|---|---|
| `municipality_code` | 예 | 지원 지자체 |
| `text` | 예 | 1~500자, 줄 수 최대 30 |

**200 응답**
```json
{
  "municipality_code": "3780000",
  "lines": [
    {
      "line_no": 1,
      "raw_text": "3인용 소파",
      "quantity": 1,
      "status": "matched",
      "needs_review": false,
      "selected_item_id": 101,
      "candidates": [
        {
          "item_id": 101,
          "name": "소파",
          "spec": "3인용",
          "fee_won": 10000,
          "fee_type": "paid",
          "score": 0.91,
          "reason": "3인용 표현이 규격과 일치합니다."
        },
        {
          "item_id": 102,
          "name": "소파",
          "spec": "2인용",
          "fee_won": 8000,
          "fee_type": "paid",
          "score": 0.63,
          "reason": "같은 품목의 다른 규격입니다."
        }
      ],
      "note": null
    },
    {
      "line_no": 3,
      "raw_text": "의자 4개",
      "quantity": 4,
      "status": "ambiguous",
      "needs_review": true,
      "selected_item_id": null,
      "candidates": [],
      "note": "규격을 선택하십시오."
    }
  ],
  "degraded": false,
  "degraded_reason": null,
  "data_base_date": "2026-11-01",
  "disclaimer": "실제 수수료와 절차는 해당 지자체의 안내를 확인하십시오."
}
```

**필드 설명**
| 필드 | 설명 |
|---|---|
| `status` | `matched`(자동 선택 가능), `ambiguous`(확인 필요), `unmatched`(후보 없음) |
| `selected_item_id` | `matched`일 때 AI가 고른 후보. **사용자가 확정해야 함** |
| `candidates` | 최대 3개, 점수 내림차순. `reason`은 한 문장 |
| `quantity` | 입력에서 추출, 없으면 1, 범위 1~99 |
| `score` | 0~1, 내부 병합 점수(정확도 확률이 아님) |

**규칙**
- 모든 `item_id`는 해당 지자체 품목이며 후보 목록 안에서만 선택됩니다.
- 금액은 후보의 `fee_won`(DB 값)만 포함하며 합계는 계산하지 않습니다.
- `degraded: true`이면 `reason`은 `null`이거나 "검색 점수 기준"으로 표기됩니다.

**오류**: `VALIDATION_ERROR`, `MUNICIPALITY_NOT_FOUND`, `RATE_LIMITED`, `DB_UNAVAILABLE`.

---

## API-05 견적·절차 생성

`POST /api/v1/estimates`

**201 응답**으로 생성 결과를 저장하고 반환합니다.

**요청**
```json
{
  "municipality_code": "3780000",
  "input_text": "3인용 소파, 책상, 의자 4개",
  "lines": [
    { "raw_text": "3인용 소파", "item_id": 101, "quantity": 1, "operator_fee_won": 30000 },
    { "raw_text": "책상", "item_id": 205, "quantity": 1 },
    { "raw_text": "의자 4개", "item_id": 310, "quantity": 4 }
  ]
}
```
| 필드 | 필수 | 제약 |
|---|---|---|
| `municipality_code` | 예 | 지원 지자체 |
| `input_text` | 아니오 | 원본 입력(최대 500자), 개인정보 입력 금지 |
| `lines[].item_id` | 예 | 해당 지자체 품목 |
| `lines[].quantity` | 예 | 1~99 정수 |
| `lines[].operator_fee_won` | 아니오 | 0 이상 정수(업체 작업비, 줄 단위, 수량과 무관한 줄 합계) |
| `lines` | 예 | 1~30개 |

**201 응답**
```json
{
  "public_id": "k3F9xQ2mZp",
  "municipality_code": "3780000",
  "lines": [
    {
      "line_no": 1,
      "raw_text": "3인용 소파",
      "item": { "item_id": 101, "name": "소파", "spec": "3인용" },
      "quantity": 1,
      "unit_fee_won": 10000,
      "fee_type": "paid",
      "municipal_fee_won": 10000,
      "operator_fee_won": 30000
    },
    {
      "line_no": 2,
      "raw_text": "책상",
      "item": { "item_id": 205, "name": "책상", "spec": "일반" },
      "quantity": 1,
      "unit_fee_won": 5000,
      "fee_type": "paid",
      "municipal_fee_won": 5000,
      "operator_fee_won": 0
    },
    {
      "line_no": 3,
      "raw_text": "의자 4개",
      "item": { "item_id": 310, "name": "의자", "spec": "일반" },
      "quantity": 4,
      "unit_fee_won": 3000,
      "fee_type": "paid",
      "municipal_fee_won": 12000,
      "operator_fee_won": 0
    }
  ],
  "totals": {
    "municipal_fee_total_won": 27000,
    "operator_fee_total_won": 30000,
    "grand_total_won": 57000
  },
  "procedure": {
    "status": "ok",
    "steps": [
      {
        "order": 1,
        "title": "배출 신고",
        "detail": "근거 문단에 있는 내용만 서술합니다.",
        "citation_ids": [12]
      }
    ],
    "checklist": [
      { "text": "배출 전 신고를 완료합니다.", "citation_ids": [12] }
    ],
    "warnings": []
  },
  "citations": [
    {
      "chunk_id": 12,
      "source_name": "성남시 대형폐기물 배출 안내",
      "section": "신고 방법",
      "base_date": "2026-11-01",
      "excerpt": "원문 일부(최대 200자)"
    }
  ],
  "degraded": false,
  "degraded_reason": null,
  "data_base_date": "2026-11-01",
  "disclaimer": "실제 수수료와 절차는 해당 지자체의 안내를 확인하십시오.",
  "created_at": "2026-11-16T09:00:00+09:00",
  "expires_at": "2026-12-16T09:00:00+09:00",
  "share_path": "/s/k3F9xQ2mZp"
}
```
(예시 금액은 형식 설명용 가상 값이며, `totals`는 서버가 줄 데이터로 계산합니다: 10,000 + 5,000 + 3,000×4 = 27,000 / 작업비 30,000 / 총 57,000.)

**수수료 유형**: `fee_type`은 `paid`(금액 있음), `free`(무료), `exempt`(면제) 중 하나입니다. `free`·`exempt`의 `fee_won`·`unit_fee_won`은 0입니다.

**계산 규칙**
- `municipal_fee_won` = `unit_fee_won` × `quantity` (`fee_type`이 `free`·`exempt`이면 0이며, 화면은 "무료"·"면제"로 표시)
- `municipal_fee_total_won` = 줄별 `municipal_fee_won` 합
- `operator_fee_total_won` = 줄별 `operator_fee_won` 합(없으면 0)
- `grand_total_won` = 두 합계의 합
- 지자체 수수료와 작업비는 항상 분리해서 표시합니다.

**`procedure.status`**
| 값 | 의미 |
|---|---|
| `ok` | 근거 기반 단계·체크리스트 생성 |
| `insufficient_evidence` | 근거 부족. `steps`는 비어 있고 `warnings`에 "해당 지자체 안내 확인 필요" |
| `raw_chunks` | 저하 모드. `steps` 대신 `citations` 원문만 제공 |
| `unsupported` | 수수료만 제공하는 지자체(`procedure_supported: false`). `steps`·`checklist`·`citations`는 비어 있고 `warnings`에 "이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오." |

**규칙**
- 요청의 금액 필드는 `operator_fee_won`만 받으며, 지자체 수수료는 서버 DB 값으로 계산합니다.
- 모든 `steps`와 `checklist`에는 존재하는 `citation_ids`가 있어야 합니다.
- 견적 시점의 단가를 저장하므로 이후 데이터가 갱신돼도 조회 결과는 변하지 않습니다.

**오류**: `VALIDATION_ERROR`, `MUNICIPALITY_NOT_FOUND`, `ITEM_NOT_IN_MUNICIPALITY`, `RATE_LIMITED`, `DB_UNAVAILABLE`.

---

## API-06 견적 조회 (공유)

`GET /api/v1/estimates/{public_id}`

**200 응답**: API-05의 201 응답과 같은 구조.

**오류**
| HTTP | code | 상황 |
|---|---|---|
| 404 | `ESTIMATE_NOT_FOUND` | 없는 ID |
| 410 | `ESTIMATE_EXPIRED` | 만료 |

조회 시 `input_text`는 반환하지 않습니다(공유 대상에게 원본 입력을 노출하지 않음).

---

## API-07 피드백 제출

`POST /api/v1/estimates/{public_id}/feedback`

**요청**
```json
{
  "line_no": 3,
  "type": "wrong_item",
  "comment": "의자 규격이 다릅니다.",
  "suggested_item_id": 311
}
```
| 필드 | 필수 | 제약 |
|---|---|---|
| `line_no` | 아니오 | 줄 번호, 전체 피드백이면 생략 |
| `type` | 예 | `wrong_item`, `wrong_fee`, `procedure_issue`, `other` |
| `comment` | 아니오 | 최대 300자, 개인정보 입력 금지 |
| `suggested_item_id` | 아니오 | `wrong_item`일 때 제안 품목 |

**201 응답**
```json
{ "feedback_id": 15, "status": "received" }
```
**오류**: `VALIDATION_ERROR`, `ESTIMATE_NOT_FOUND`, `ESTIMATE_EXPIRED`, `RATE_LIMITED`.

---

## API-08 절차 질문 (Could)

`POST /api/v1/qa`

**요청**
```json
{ "municipality_code": "3780000", "question": "소파는 어디에 내놓아야 하나요?" }
```
| 필드 | 제약 |
|---|---|
| `question` | 1~200자 |

**200 응답**
```json
{
  "answerable": true,
  "answer": "근거 문단에 있는 내용만 답합니다.",
  "citations": [
    { "chunk_id": 12, "source_name": "성남시 대형폐기물 배출 안내", "section": "배출 장소", "base_date": "2026-11-01", "excerpt": "..." }
  ],
  "data_base_date": "2026-11-01",
  "disclaimer": "실제 수수료와 절차는 해당 지자체의 안내를 확인하십시오."
}
```
- 근거가 없으면 `answerable: false`, `answer`는 "해당 내용은 안내문에서 확인되지 않습니다. 지자체에 문의하십시오."이며 `citations`는 빈 배열.
- 수수료만 제공하는 지자체이면 `answerable: false`, `answer`는 "이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오."입니다.
- LLM을 쓸 수 없으면 `503 LLM_UNAVAILABLE`.

---

## 부록 A. 상태 코드 요약

| 코드 | 사용 |
|---|---|
| 200 | 조회·분석 성공 |
| 201 | 견적·피드백 생성 |
| 400 | 검증 오류 |
| 404 | 대상 없음 |
| 410 | 만료 |
| 429 | 한도 초과 |
| 500 / 503 | 서버·DB·LLM 장애 |

## 부록 B. 필드 제약 요약

| 필드 | 제약 |
|---|---|
| `text`, `input_text` | 1~500자 (`input_text`는 선택) |
| 줄 수 | 최대 30 |
| `quantity` | 1~99 정수 |
| `operator_fee_won` | 0 이상 정수 |
| `public_id` | 영숫자 약 10자, 추측 불가한 무작위 값 |
| 만료 | 생성 후 30일 |

## 부록 C. 변경 관리
- 이 문서가 구현의 기준입니다. 구현 중 변경이 필요하면 변경안을 사용자에게 제안하고 승인 후에 문서를 갱신합니다.
- 응답에 필드를 추가하는 것은 하위 호환이며, 필드 삭제·이름 변경은 `/api/v2` 대상입니다.
