/**
 * Copilot chat types — single source of truth for store + sse-client + components.
 * Mirrors backend Pydantic schemas (app/modules/copilot/schemas.py).
 */

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  /** Present on assistant messages when streaming failed. */
  error?: string;
  /** VRL block extracted after streaming ends. */
  vrlBlock?: string;
};

export type ParseResult = {
  index: number;
  status: "ok" | "error";
  message?: string;
};

export type MatchHypothesis = {
  vendorSlug: string;
  productSlug: string;
  logTypeName: string;
  confidence: number;
};

export type FieldSummary = {
  name: string;
  type: string;
  required: boolean;
};

export type ActiveLogTypeContext = {
  name: string;
  fields: FieldSummary[];
  samplesCount: number;
  parseRuleHead: string | null;
};

export type VersionDiffContext = {
  baseVersion: string;
  headVersion: string;
  baseVrl: string | null;
  headVrl: string | null;
};

export type AnalyzerPageContext = {
  page: "analyzer";
  vrl: string | null;
  vrlEngine: string | null;
  logs: string[];
  parseResults: ParseResult[];
  matchTopCandidate: MatchHypothesis | null;
};

export type LibraryOverviewPageContext = {
  page: "library_overview";
  filters: { status?: string | null; q?: string | null };
  vendorCount: number;
  productCount: number;
  productsMissingParseRule: string[];
};

export type LibraryProductPageContext = {
  page: "library_product";
  vendorSlug: string;
  productSlug: string;
  productStatus: string;
  activeLogType: ActiveLogTypeContext | null;
};

export type LibraryVersionsPageContext = {
  page: "library_versions";
  vendorSlug: string;
  productSlug: string;
  logTypeName: string;
  diff: VersionDiffContext | null;
};

export type PageContext =
  | AnalyzerPageContext
  | LibraryOverviewPageContext
  | LibraryProductPageContext
  | LibraryVersionsPageContext;

export type ChatRequestBody = {
  messages: { role: ChatRole; content: string }[];
  skill: SkillName | null;
  page_context: BackendPageContext | null;
};

/** Snake-case shape sent to the backend. Discriminated union mirroring PageContext. */
export type BackendAnalyzerPageContext = {
  page: "analyzer";
  vrl: string | null;
  vrl_engine: string | null;
  logs: string[];
  parse_results: { index: number; status: "ok" | "error"; message?: string }[];
  match_top_candidate: {
    vendor_slug: string;
    product_slug: string;
    log_type_name: string;
    confidence: number;
  } | null;
};

export type BackendLibraryOverviewPageContext = {
  page: "library_overview";
  filters: { status?: string | null; q?: string | null };
  vendor_count: number;
  product_count: number;
  products_missing_parse_rule: string[];
};

export type BackendLibraryProductPageContext = {
  page: "library_product";
  vendor_slug: string;
  product_slug: string;
  product_status: string;
  active_log_type: {
    name: string;
    fields: FieldSummary[];
    samples_count: number;
    parse_rule_head: string | null;
  } | null;
};

export type BackendLibraryVersionsPageContext = {
  page: "library_versions";
  vendor_slug: string;
  product_slug: string;
  log_type_name: string;
  diff: {
    base_version: string;
    head_version: string;
    base_vrl: string | null;
    head_vrl: string | null;
  } | null;
};

export type BackendPageContext =
  | BackendAnalyzerPageContext
  | BackendLibraryOverviewPageContext
  | BackendLibraryProductPageContext
  | BackendLibraryVersionsPageContext;

export type SSEEvent =
  | { type: "text_delta"; text: string }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

export type SkillName = "log_explain" | "vrl_generate";

export type EditorBridge = {
  setVrl: ((next: string) => void) | null;
  getVrl: () => string;
};

export type PendingInsert = {
  proposedVrl: string;
  messageId: string;
};
