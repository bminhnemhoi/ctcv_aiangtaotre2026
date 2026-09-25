/**
 * "Nguồn" panel (idea §4, invariant 3): for every citation, the page title, the portal or
 * agency, the day it was fetched, the quoted passage and a link to the official page.
 */
import type { Citation } from '../api/types';
import { vi } from '../i18n/vi';

/** Vietnam is UTC+7 all year (no daylight saving). */
const VN_OFFSET_MS = 7 * 60 * 60 * 1000;
const DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/** `2026-09-24T18:30:00Z` → `25/09/2026` (Vietnam date); `null` when not a date. */
export function formatVnDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const dateOnly = DATE_ONLY_RE.exec(value);
  if (dateOnly) return `${dateOnly[3]}/${dateOnly[2]}/${dateOnly[1]}`;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return null;
  const local = new Date(ms + VN_OFFSET_MS);
  return `${pad2(local.getUTCDate())}/${pad2(local.getUTCMonth() + 1)}/${local.getUTCFullYear()}`;
}

/** Only `https://` links are ever rendered (no `javascript:`, no plain http). */
export function isSafeHttpsUrl(url: string | null | undefined): url is string {
  if (!url) return false;
  try {
    return new URL(url).protocol === 'https:';
  } catch {
    return false;
  }
}

export interface OfficialLinkProps {
  href: string;
  label: string;
}

/** Big, underlined link to an official page, opened in a new page without referrer. */
export function OfficialLink({ href, label }: OfficialLinkProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="flex min-h-tap items-center justify-center rounded-2xl border-4 border-xanh bg-trang px-lg py-sm text-center text-lg font-bold text-xanh underline"
    >
      {label}
      <span className="sr-only"> {vi.source.newWindow}</span>
    </a>
  );
}

function SourceItem({ citation }: { citation: Citation }) {
  const origin = citation.source_portal || citation.agency;
  const fetchedOn = formatVnDate(citation.fetched_at);
  return (
    <li className="flex flex-col gap-sm">
      <p className="text-lg font-bold leading-snug text-den">{citation.title}</p>
      {origin ? <p className="text-base text-den">{`${vi.source.from} ${origin}`}</p> : null}
      {fetchedOn ? (
        <p className="text-base text-den">{`${vi.source.fetchedOn} ${fetchedOn}`}</p>
      ) : null}
      {citation.quote ? (
        <blockquote className="border-l-8 border-xam pl-md text-base leading-snug text-den">
          “{citation.quote}”
        </blockquote>
      ) : null}
      {isSafeHttpsUrl(citation.url) ? (
        <OfficialLink href={citation.url} label={vi.source.openOfficial} />
      ) : null}
    </li>
  );
}

export interface SourcePanelProps {
  id: string;
  citations: readonly Citation[];
}

export function SourcePanel({ id, citations }: SourcePanelProps) {
  const titleId = `${id}-title`;
  return (
    <section
      id={id}
      data-testid="source-panel"
      aria-labelledby={titleId}
      className="flex flex-col gap-md rounded-2xl border-4 border-xanh bg-trang p-md"
    >
      <h3 id={titleId} className="text-lg font-bold text-xanh">
        {vi.source.heading}
      </h3>
      <ul className="flex flex-col gap-lg">
        {citations.map((citation, index) => (
          <SourceItem key={`${citation.doc_id}-${index}`} citation={citation} />
        ))}
      </ul>
    </section>
  );
}
