export type FeeType = "paid" | "free" | "exempt";

export interface Municipality {
  code: string;
  name: string;
  support_level: "fee_and_procedure" | "fee_only";
  procedure_supported: boolean;
  spec_missing: boolean;
  data_base_date: string | null;
  legal_effective_date: string | null;
  item_count: number;
}

export interface SearchItem {
  item_id: number;
  category: string;
  name: string;
  spec: string;
  fee_won: number;
  fee_type: FeeType;
  score: number;
}

export interface ParseCandidate extends SearchItem {
  reason: string;
}

export interface ParseLine {
  line_no: number;
  raw_text: string;
  quantity: number;
  status: "matched" | "ambiguous" | "unmatched";
  needs_review: boolean;
  selected_item_id: number | null;
  candidates: ParseCandidate[];
  note: string | null;
}

export interface ParseResult {
  municipality_code: string;
  lines: ParseLine[];
  degraded: boolean;
  degraded_reason: string | null;
  data_base_date: string | null;
  disclaimer: string;
}

export interface EstimateLineOut {
  line_no: number;
  raw_text: string | null;
  item: { item_id: number; name: string; spec: string };
  quantity: number;
  unit_fee_won: number;
  fee_type: FeeType;
  municipal_fee_won: number;
  operator_fee_won: number;
}

export interface Procedure {
  status: "ok" | "insufficient_evidence" | "raw_chunks" | "unsupported";
  steps: { order: number; title: string; detail: string; citation_ids: number[] }[];
  checklist: { text: string; citation_ids: number[] }[];
  warnings: string[];
}

export interface Citation {
  chunk_id: number;
  source_name: string;
  section: string;
  base_date: string | null;
  excerpt: string;
}

export interface Estimate {
  public_id: string;
  municipality_code: string;
  lines: EstimateLineOut[];
  totals: { municipal_fee_total_won: number; operator_fee_total_won: number; grand_total_won: number };
  procedure: Procedure;
  citations: Citation[];
  degraded: boolean;
  degraded_reason: string | null;
  data_base_date: string | null;
  disclaimer: string;
  created_at: string;
  expires_at: string;
  share_path: string;
}

export interface EstimateRequest {
  municipality_code: string;
  input_text?: string;
  lines: { raw_text?: string; item_id: number; quantity: number; operator_fee_won?: number }[];
}
