/**
 * Wire types of the `/v1` routes used by the web app (ADR-007 contract C6).
 *
 * Optional fields may arrive as `null` (Pydantic `None`) or be missing altogether, so every
 * optional field is typed `T | null` and marked `?`.
 */

/** Roles issued by `/v1/auth/*` (config/app.yaml `roles`). */
export type Role = 'citizen' | 'volunteer' | 'officer';

/** `POST /v1/auth/join` and `POST /v1/auth/login` — 200 body. */
export interface AuthOut {
  token: string;
  user_id: string;
  role: Role;
}

/** Why the coach answered the way it did. */
export type AskReason =
  | 'ok'
  | 'no_source'
  | 'sensitive'
  | 'real_action'
  | 'pasted_content'
  | 'verify_failed'
  | 'kb_not_ready';

/** How the answer was produced. */
export type AnswerMode = 'llm_verified' | 'template' | 'safety' | 'no_source';

/** One official source backing the answer. */
export interface Citation {
  doc_id: string;
  title: string;
  url: string;
  quote?: string | null;
  agency?: string | null;
  source_portal?: string | null;
  /** ISO date-time (UTC, `Z`) when the page was fetched. */
  fetched_at?: string | null;
  effective_date?: string | null;
  section?: string | null;
  procedure_id?: string | null;
}

/** A procedure as referenced by the answer or the intake check. */
export interface ProcedureRef {
  procedure_id: string;
  ten: string;
  co_quan: string | null;
  source_url: string;
  fetched_at: string;
}

/** One document of a procedure file. */
export interface DocItem {
  /** `d01`, `d02`, … */
  doc_key: string;
  name: string;
  case_label: string | null;
  originals: number | null;
  copies: number | null;
  form_code: string | null;
  /**
   * `true` when the document is needed only in a special situation named in its own text
   * ("Trường hợp người … định cư ở nước ngoài …"). Optional: older API versions omit it.
   */
  conditional?: boolean | null;
}

/** Fee and time limit for one submission channel. */
export interface FeeItem {
  channel: string;
  channel_text: string;
  time_limit: string | null;
  fee_text: string | null;
  amounts_vnd: number[];
}

/** Procedure card returned with an answer. */
export interface ProcedureCard extends ProcedureRef {
  documents: DocItem[];
  fees: FeeItem[];
  cases: string[];
}

/** `POST /v1/coach/ask` — request body. */
export interface AskIn {
  question: string;
  session_id?: string;
}

/** `POST /v1/coach/ask` — 200 body. */
export interface AskOut {
  answer: string;
  citations: Citation[];
  confidence: number;
  escalate: boolean;
  refused: boolean;
  reason: AskReason;
  answer_mode: AnswerMode;
  procedure: ProcedureCard | null;
}

/** `POST /v1/coach/intake-check` — request body (exactly one of `procedure_id`, `query`). */
export interface IntakeCheckIn {
  procedure_id?: string;
  query?: string;
  received: string[];
  case_label?: string;
}

/**
 * Status of one document in the intake checklist. `neu_ap_dung` ("only if it applies") marks a
 * conditional document that was not received: it is never counted as missing.
 */
export type ChecklistStatus = 'da_nhan' | 'thieu' | 'neu_ap_dung';

export interface ChecklistItem extends DocItem {
  status: ChecklistStatus;
}

/** `POST /v1/coach/intake-check` — 200 body. */
export interface IntakeCheckOut {
  procedure: ProcedureRef;
  alternatives: ProcedureRef[];
  cases: string[];
  needs_case: boolean;
  items: ChecklistItem[];
  missing_count: number;
  message_for_citizen: string;
  citations: Citation[];
}
