# 대형폐기물 배출 플래너

이사·정리 업체 담당자가 고객의 물건 목록으로 지자체 대형폐기물 수수료와 배출 절차를 근거와 함께 안내하는 도구입니다. 문서는 `docs/`를 참조하십시오.

## 구성
- `docs/` 기획 문서(PRD, SDD, API 계획·정의서, 아키텍처, 평가 계획, 데이터 이용조건)
- `data/raw/` 원본, `data/processed/` 정제 결과
- `scripts/` 데이터 추출·정제 스크립트
- `backend/` FastAPI 서버, `db/schema.sql` DB 스키마

> 처음 시작은 `docs/08_DEV_GUIDE.md`를 순서대로 따르십시오.

## 로컬 실행 (backend)
```
cd backend
uv sync
cp ../.env.example .env      # 값 입력(키는 커밋 금지)
uv run uvicorn app.main:app --reload
uv run pytest
```

## 데이터 준비
```
python scripts/extract_seongnam_pdf.py <별표.pdf> data/processed/seongnam_fees.csv   # 필요 시
python scripts/prepare_data.py --national data/raw/national_fees.csv \
  --seongnam data/processed/seongnam_fees.csv --misc data/processed/seongnam_fees_misc.csv
```
결과: `data/processed/municipalities.csv`, `item_catalog.csv`, `waste_items.csv`, 점검 리포트 `docs/research/data_check.md`.
