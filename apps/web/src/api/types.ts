export type ProfileCode = "conservative" | "balanced" | "aggressive";

export interface Score {
  margin: number | null;
  base: number | null;
  risk: number | null;
  stability: number | null;
  total: number | null;
  band: string;
}

export interface RankingItem {
  valuation_market_id: number;
  report_id: number;
  instrument_id: number;
  name: string;
  market: string;
  code: string;
  currency: string;
  industry: string;
  path: string;
  analysis_date: string;
  stale_days: number;
  price: number;
  price_date: string;
  fair_low: number;
  fair_mid: number;
  fair_high: number;
  safety_margin_pct: number | null;
  expected_return: Record<string, number | null>;
  max_drawdown_pct: number | null;
  verdict: string;
  thesis: string;
  confidence: string;
  rank: number | null;
  score: Score;
  base_income: number | null;
  risk_adjusted_ratio: number | null;
  value_reliance: number;
  risk_flags: string[];
  excluded_reasons: string[];
  is_etf: boolean;
}

export interface Freshness {
  ranking_as_of: string;
  latest_analysis_date: string | null;
  latest_price_date: string | null;
  stale_after_days: number;
  stale_units: number;
  status: string;
}

export interface RankingResponse {
  profile: ProfileCode;
  profile_label: string;
  algorithm_version: string;
  main_board: RankingItem[];
  etfs: RankingItem[];
  excluded: RankingItem[];
  top_three: RankingItem[];
  counts: Record<string, number>;
  freshness: Freshness;
  available_industries: string[];
  available_paths: string[];
  available_markets: string[];
}

export interface ValuationDetail {
  valuation_market_id: number;
  report_id: number;
  instrument_id: number;
  name: string;
  market: string;
  code: string;
  currency: string;
  asset_type: string;
  path: string;
  industry: string;
  analysis_date: string;
  generated_at: string | null;
  price_date: string;
  stale_days: number;
  quality: {
    rating: number;
    label: string;
    score: number;
    moat: string;
    gate_pass: boolean;
    gate_reason: string;
  };
  cycle: {
    stage: string;
    position: number | null;
  };
  conclusion: {
    verdict: string;
    thesis: string;
    confidence: string;
  };
  price: number;
  baseline_price: number;
  current_price: number;
  fair_low: number;
  fair_mid: number;
  fair_high: number;
  safety_margin_pct: number | null;
  effective_safety_margin_pct: number | null;
  valuation: Record<string, number | null>;
  gauges: Record<string, number>;
  expected_return: Record<string, number | null>;
  downside: {
    max_drawdown_pct?: number | null;
    scenario?: string;
  };
  position: {
    base_pct?: number;
    target_pct?: number;
    cap_pct?: number;
    buy_points?: string;
  };
  verdict: string;
  score: Score;
  risks: string[];
  missing: string[];
  notes: string;
  risk_flags: string[];
  excluded_reasons: string[];
  same_company: Array<{
    valuation_market_id: number;
    market: string;
    code: string;
    currency: string;
    price: number;
    fair_mid: number;
    safety_margin_pct: number | null;
    verdict: string;
  }>;
  report_url: string | null;
}

export interface RankingFilters {
  profile: ProfileCode;
  market?: string;
  path?: string;
  industry?: string;
  staleOnly?: boolean;
}

export interface Schedule {
  enabled: boolean;
  frequency: "trading_daily" | "weekly" | "manual";
  run_time: string;
  timezone: string;
  calendar_mode: "CN" | "HK" | "ANY";
  scope: "all";
  revaluation_mode: "weekly_event" | "weekly" | "trading_daily" | "off";
  publish_mode: "review_all" | "review_exceptions" | "auto";
  stale_after_days: number;
  next_run_at: string | null;
  updated_at: string;
}

export interface SchedulePatch {
  enabled?: boolean;
  frequency?: Schedule["frequency"];
  run_time?: string;
  calendar_mode?: Schedule["calendar_mode"];
  stale_after_days?: number;
  revaluation_mode?: Schedule["revaluation_mode"];
  publish_mode?: Schedule["publish_mode"];
}

export interface Job {
  id: number;
  job_type: string;
  trigger: string;
  scope: string;
  status: string;
  phase: string;
  scheduled_for: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface JobList {
  items: Job[];
}
