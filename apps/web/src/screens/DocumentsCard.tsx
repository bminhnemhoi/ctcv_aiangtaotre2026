/**
 * "Giấy tờ cần chuẩn bị": the official document list of a procedure as big tick boxes,
 * grouped by case. Ticks live in component state only (never stored or sent anywhere).
 * Long official names and case labels show a preview first, with a "Xem đủ" button.
 */
import { useId, useState } from 'react';
import type { ChecklistStatus, DocItem, ProcedureCard } from '../api/types';
import { ExpandToggle, previewText, useExpandable } from '../components/ExpandableText';
import { vi } from '../i18n/vi';

/**
 * `Tờ khai (bản chính: 1, bản sao: 0, mẫu CT01)` — only the parts the source gives. `name`
 * replaces the document name (its preview) while the copy counts always stay visible.
 */
export function describeDoc(doc: DocItem, name: string = doc.name): string {
  const parts: string[] = [];
  if (doc.originals !== null && doc.originals !== undefined) {
    parts.push(`${vi.docs.originals}: ${doc.originals}`);
  }
  if (doc.copies !== null && doc.copies !== undefined) {
    parts.push(`${vi.docs.copies}: ${doc.copies}`);
  }
  if (doc.form_code) parts.push(`${vi.docs.form} ${doc.form_code}`);
  return parts.length > 0 ? `${name} (${parts.join(', ')})` : name;
}

/** Needed only in a special situation: the `conditional` flag or the `neu_ap_dung` status. */
export function isConditional(doc: DocItem & { status?: ChecklistStatus }): boolean {
  return doc.conditional === true || doc.status === 'neu_ap_dung';
}

/** Lead-in tail of a case label: "…, hồ sơ gồm:", "… bao gồm", "… gồm". */
const CASE_TAIL = /(?:[,;]?\s*hồ sơ)?\s+(?:bao\s+)?gồm$/iu;
const TRAILING_PUNCT = /[\s,;:]+$/u;

/**
 * A case label as shown on screen. The source's lead-in sentence ("Hồ sơ đăng ký tạm trú gồm")
 * loses its "gồm"/":" tail; the raw label is still what the API receives.
 */
export function displayCaseLabel(label: string): string {
  const trimmed = label.normalize('NFC').trim().replace(TRAILING_PUNCT, '');
  const short = trimmed.replace(CASE_TAIL, '').replace(TRAILING_PUNCT, '');
  return short || trimmed || label;
}

/**
 * Text of each case in a drop-down: the preview of `displayCaseLabel`, or the whole label when
 * two previews would read the same (the officer must never pick the wrong case).
 */
export function caseOptionLabels(cases: readonly string[]): string[] {
  const shown = cases.map(displayCaseLabel);
  const previews = shown.map((text) => previewText(text) ?? text);
  return previews.map((text, i) =>
    previews.indexOf(text) === previews.lastIndexOf(text) ? text : (shown[i] ?? text),
  );
}

export interface DocGroup<T extends DocItem> {
  label: string | null;
  items: T[];
}

/** Group by `case_label`, common documents (no label) first, then cases in source order. */
export function groupDocuments<T extends DocItem>(docs: readonly T[]): DocGroup<T>[] {
  const groups = new Map<string | null, T[]>([[null, []]]);
  for (const doc of docs) {
    const label = doc.case_label || null;
    const bucket = groups.get(label) ?? [];
    bucket.push(doc);
    groups.set(label, bucket);
  }
  return [...groups.entries()]
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

export interface CheckItemProps {
  testId: string;
  doc: DocItem & { status?: ChecklistStatus };
  checked: boolean;
  onToggle: () => void;
}

/**
 * A whole-row tick box (row ≥ 56 px tall, box 40 px) — the label text is clickable too. A long
 * name shows its preview and a "Xem đủ" button below the label (outside it, so opening the text
 * never ticks the box); a conditional document starts with a yellow "only if it applies" tag.
 */
export function CheckItem({ testId, doc, checked, onToggle }: CheckItemProps) {
  const textId = useId();
  const name = useExpandable(doc.name);
  return (
    <div
      data-testid={`doc-row-${doc.doc_key}`}
      className={`flex flex-col gap-sm rounded-2xl border-4 bg-trang px-md py-sm ${checked ? 'border-xanh' : 'border-xam'}`}
    >
      <label className="flex min-h-tap cursor-pointer items-center gap-md">
        <input
          type="checkbox"
          data-testid={testId}
          checked={checked}
          onChange={onToggle}
          className="h-10 w-10 shrink-0 cursor-pointer accent-xanh"
        />
        <span id={textId} className="text-base leading-snug text-den">
          {isConditional(doc) ? (
            <span className="mb-xs block w-fit rounded-lg bg-vang px-xs font-bold text-den">
              {`${vi.docs.conditional} `}
            </span>
          ) : null}
          {describeDoc(doc, name.shown)}
        </span>
      </label>
      <ExpandToggle state={name} controls={textId} testId={`more-${testId}`} className="ml-tap" />
    </div>
  );
}

export interface GroupLegendProps {
  /** Raw case label (`null` = the common documents). */
  label: string | null;
  className: string;
}

/** Legend of a document group; a long case label gets its own "Xem đủ" button. */
export function GroupLegend({ label, className }: GroupLegendProps) {
  const textId = useId();
  const text = useExpandable(label ? displayCaseLabel(label) : vi.docs.commonGroup);
  return (
    <>
      <legend id={textId} className={className}>
        {text.shown}
      </legend>
      <ExpandToggle state={text} controls={textId} />
    </>
  );
}

/** Toggle helper shared by the citizen card and the officer checklist. */
export function toggleKey(set: ReadonlySet<string>, key: string): ReadonlySet<string> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

export interface DocumentsCardProps {
  procedure: ProcedureCard;
}

export function DocumentsCard({ procedure }: DocumentsCardProps) {
  const headingId = useId();
  const [checked, setChecked] = useState<ReadonlySet<string>>(() => new Set());
  const groups = groupDocuments(procedure.documents);
  const showLegends = groups.length > 1 || groups[0]?.label !== null;
  return (
    <section
      data-testid="docs-card"
      aria-labelledby={headingId}
      className="flex flex-col gap-md rounded-2xl border-4 border-xam bg-trang p-md"
    >
      <h2 id={headingId} className="text-xl font-bold text-xanh">
        {vi.docs.heading}
      </h2>
      <p className="text-base font-semibold text-den">{`${vi.docs.procedure} ${procedure.ten}`}</p>
      <p className="text-base text-den">{vi.docs.hint}</p>
      {groups.map((group) => (
        <fieldset key={group.label ?? ''} className="flex flex-col gap-sm">
          {showLegends ? (
            <GroupLegend label={group.label} className="pb-xs text-lg font-bold text-den" />
          ) : null}
          {group.items.map((doc) => (
            <CheckItem
              key={doc.doc_key}
              testId={`doc-item-${doc.doc_key}`}
              doc={doc}
              checked={checked.has(doc.doc_key)}
              onToggle={() => setChecked((prev) => toggleKey(prev, doc.doc_key))}
            />
          ))}
        </fieldset>
      ))}
    </section>
  );
}
