// Shape of out/status.json (produced by scripts/cockpit.py). Loosely typed —
// fields are optional so the UI degrades gracefully on partial data.

export interface Signal {
  signal: boolean;
  close: number;
  target_weight: number;
}

export interface Paper {
  equity?: number;
  peak_equity?: number;
  drawdown?: number;
  days_recorded?: number;
  breaker_cooldown_left?: number;
  open_weights?: Record<string, number>;
}

export interface GridRow {
  lookback?: number;
  sharpe?: number;
  total_return?: number;
  max_drawdown?: number;
  cagr?: number;
}

export interface MonteCarlo {
  return_1y?: Record<string, number>;
  max_drawdown_1y?: Record<string, number>;
  prob_positive_year?: number;
  prob_dd_exceeds_10pct?: number;
  prob_dd_exceeds_15pct?: number;
  caveat?: string;
}

export interface Stress {
  base?: Record<string, number>;
  flash_crash?: {
    portfolio_loss_on_crash_day?: number;
    gross_exposure_going_in?: number;
  };
  worst_year?: { window?: string; net_return?: number };
  ragged_data?: { pipeline_survived?: boolean };
  monte_carlo?: MonteCarlo;
}

export interface Status {
  generated_utc?: string;
  data_mode?: "real" | "synthetic";
  stale_data_warnings?: string[];
  regime?: {
    state?: string;
    exposure_multiplier?: number;
    gross_scale?: number;
    as_of?: string;
  };
  carry?: {
    signal?: "IN" | "OUT";
    trailing_7d_funding_annualized?: number;
    enter_hurdle?: number;
  };
  risk?: Record<string, string | number>;
  paper?: Paper;
  equity_history?: number[];
  backtest_gate?: "PASS" | "FAIL";
  backtest?: { pass?: boolean; grid?: GridRow[]; walk_forward?: GridRow[] };
  signals?: Record<string, Signal>;
  decision?: { stage?: "DEMO" | "PAPER" | "TESTNET" | "LIVE"; line?: string };
  stress?: Stress;
}
