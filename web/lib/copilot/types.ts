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

export type PageContext = {
  page: "analyzer";
  vrl: string | null;
  vrlEngine: string | null;
  logs: string[];
  parseResults: ParseResult[];
  matchTopCandidate: MatchHypothesis | null;
};

export type ChatRequestBody = {
  messages: { role: ChatRole; content: string }[];
  skill: "log_explain" | null;
  page_context: BackendPageContext | null;
};

/** Snake-case shape sent to the backend. */
export type BackendPageContext = {
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

export type SSEEvent =
  | { type: "text_delta"; text: string }
  | { type: "error"; code: string; message: string }
  | { type: "done" };
