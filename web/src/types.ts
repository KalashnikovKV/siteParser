export interface PartsBrief {
  cpu: string | null;
  gpu: string | null;
  ram: string | null;
  ram_gb: number | null;
  motherboard: string | null;
  chipset: string | null;
  socket: string | null;
  psu: string | null;
  storage: string | null;
  is_desktop: boolean | null;
  is_laptop: boolean | null;
}

export interface PlanItem {
  role: string;
  action: "keep" | "buy";
  name: string;
  price_eur: number;
  reason: string;
}

export interface BuildPlan {
  items: PlanItem[];
  upgrade_cost_eur: number;
  listing_price_eur: number | null;
  total_in_eur: number | null;
  resale_eur: number | null;
  profit_eur: number | null;
  notes: string[];
}

export interface Analysis {
  score: number;
  verdict: string;
  platform_score: number;
  headroom_score: number;
  expandability_score: number;
  value_score: number;
  has_potential: boolean;
  socket: string | null;
  reasons: string[];
  upgrades: string[];
  plan?: BuildPlan;
  has_description?: boolean;
  price_note?: string | null;
}

export interface PricePoint {
  price_cents: number | null;
  seen_at: string;
}

export interface Advice {
  action: "buy" | "inspect" | "skip" | string;
  interest: number;
  summary: string;
  flags: string[];
  keep?: string[];
  risks?: string[];
  model?: string;
}

export interface ListingCard {
  id: string;
  url: string;
  title: string | null;
  price_cents: number | null;
  price_eur: number | null;
  city: string | null;
  condition: string | null;
  score: number | null;
  verdict: string | null;
  socket: string | null;
  has_potential: boolean;
  has_description?: boolean;
  source?: string;
  is_desktop: boolean;
  is_active: boolean;
  last_seen_at: string | null;
  upgrade_cost_eur: number | null;
  resale_eur: number | null;
  profit_eur: number | null;
  parts: PartsBrief;
  analysis: Analysis | null;
  advice?: Advice | null;
}

export interface ListingDetail extends ListingCard {
  description: string | null;
  attributes: Record<string, string>;
  price_points: PricePoint[];
  first_seen_at: string | null;
  last_detail_at: string | null;
}

export interface ListingPage {
  items: ListingCard[];
  total: number;
  page: number;
  limit: number;
}

export interface PicksPage {
  items: ListingCard[];
  total: number;
  source: "advice" | "rules" | string;
  title: string;
}

export interface Stats {
  total: number;
  active: number;
  with_details: number;
  analyzed: number;
  with_potential: number;
  advised: number;
  /** Стационарные в продаже — то же множество, что «Все». */
  on_sale: number;
  details_missing: number;
  details_stale: number;
  details_fresh: number;
  unanalyzed: number;
  detail_ttl_days: number;
  last_run: {
    started_at: string;
    finished_at: string | null;
    list_url: string | null;
    listings_seen: number;
    new_listings: number;
  } | null;
}

export interface Filters {
  cities: string[];
  sockets: string[];
  sources: string[];
  advice_counts?: Record<string, number>;
  presets?: string[];
}

export interface SourceInfo {
  name: string;
  title: string;
  homepage: string;
}

export interface QueryState {
  q: string;
  min_price: string;
  max_price: string;
  city: string;
  socket: string;
  source: string;
  potential: string;
  advice: string;
  min_score: string;
  min_profit: string;
  has_description: string;
  preset: string;
  kind: string;
  sort: string;
  page: number;
}

export interface JobStatus {
  running: boolean;
  kind: "analyze" | "details" | "advise" | null;
  done: number;
  total: number;
  analyzed: number;
  error: string | null;
  stats: Stats | null;
}

export interface AdvisorStatus {
  available: boolean;
  backend: string;
  model: string | null;
  error: string | null;
  job?: JobStatus;
}
