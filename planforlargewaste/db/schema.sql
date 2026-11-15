-- 대형폐기물 배출 플래너 DB 스키마 (SDD 5절)
-- Supabase SQL Editor에서 실행. 임베딩 차원은 모델 확정 후 맞춘다 [검증 필요].
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS municipalities (
  code                 text PRIMARY KEY,           -- 행정기관코드 7자리(전국 데이터의 제공기관코드)
  name                 text NOT NULL,
  support_level        text NOT NULL CHECK (support_level IN ('fee_and_procedure', 'fee_only')),
  procedure_supported  boolean NOT NULL DEFAULT false,
  spec_missing         boolean NOT NULL DEFAULT false,
  data_base_date       date,
  legal_effective_date date,
  item_count           integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS item_catalog (
  id          bigint PRIMARY KEY,
  name        text NOT NULL,
  spec        text NOT NULL,
  name_norm   text NOT NULL,
  spec_norm   text NOT NULL,
  search_text text NOT NULL,
  embedding   vector(768),                         -- 차원은 임베딩 모델 확정 후 조정
  UNIQUE (name_norm, spec_norm)
);
CREATE INDEX IF NOT EXISTS item_catalog_trgm ON item_catalog USING gin (search_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS waste_items (
  id                bigserial PRIMARY KEY,
  municipality_code text NOT NULL REFERENCES municipalities(code),
  catalog_id        bigint NOT NULL REFERENCES item_catalog(id),
  category          text,
  name              text NOT NULL,
  spec              text NOT NULL,
  fee_won           integer NOT NULL CHECK (fee_won >= 0),
  fee_type          text NOT NULL CHECK (fee_type IN ('paid', 'free', 'exempt')),
  source_dataset    text,
  base_date         date
);
CREATE INDEX IF NOT EXISTS waste_items_muni_catalog ON waste_items (municipality_code, catalog_id);

CREATE TABLE IF NOT EXISTS procedure_chunks (
  id                bigserial PRIMARY KEY,
  municipality_code text NOT NULL REFERENCES municipalities(code),
  source_name       text NOT NULL,
  section           text,
  content           text NOT NULL,
  embedding         vector(768),
  base_date         date
);

CREATE TABLE IF NOT EXISTS estimates (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  public_id           text UNIQUE NOT NULL,
  municipality_code   text NOT NULL REFERENCES municipalities(code),
  input_text          text,
  municipal_fee_total integer NOT NULL,
  operator_fee_total  integer NOT NULL DEFAULT 0,
  procedure_json      jsonb,
  degraded            boolean NOT NULL DEFAULT false,
  created_at          timestamptz NOT NULL DEFAULT now(),
  expires_at          timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS estimate_lines (
  id               bigserial PRIMARY KEY,
  estimate_id      uuid NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
  line_no          integer NOT NULL,
  raw_text         text,
  item_id          bigint REFERENCES waste_items(id),
  quantity         integer NOT NULL CHECK (quantity BETWEEN 1 AND 99),
  unit_fee_won     integer NOT NULL,
  fee_type         text NOT NULL,
  operator_fee_won integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS feedback (
  id                bigserial PRIMARY KEY,
  estimate_id       uuid REFERENCES estimates(id) ON DELETE CASCADE,
  line_no           integer,
  type              text NOT NULL,
  comment           text,
  suggested_item_id bigint,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_counters (
  counter_key text PRIMARY KEY,                     -- 예: llm:2026-11-18, ip:<해시>:<분>
  count       integer NOT NULL DEFAULT 0,
  expires_at  timestamptz NOT NULL
);
