/**
 * One-stop intake check (#can-bo, ADR-007 C7): a staff member finds the procedure, ticks the
 * documents the citizen brought, and gets the missing list plus a short message to hand back.
 * Backed by `/v1/coach/intake-check` (rules only, no language model). Nothing is stored.
 */
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { ApiError, type ApiClient } from '../api/client';
import type { ChecklistItem, IntakeCheckIn, IntakeCheckOut } from '../api/types';
import { BigButton } from '../components/BigButton';
import { vi } from '../i18n/vi';
import { useSession } from '../state/session';
import { ExpandToggle, useExpandable } from '../components/ExpandableText';
import {
  CheckItem,
  GroupLegend,
  caseOptionLabels,
  describeDoc,
  groupDocuments,
  isConditional,
  toggleKey,
} from './DocumentsCard';
import { OfficerLogin, STAFF_ROLES } from './OfficerLogin';
import { OfficialLink, formatVnDate, isSafeHttpsUrl } from './SourcePanel';

/** Shortest procedure name `/v1/coach/intake-check` accepts. */
export const MIN_QUERY_CHARS = 2;

const FIELD_CLASS =
  'min-h-tap w-full rounded-2xl border-4 border-xam bg-trang px-md py-sm text-lg text-den';

type Busy = 'search' | 'case' | 'check' | null;

/** Items shown for the chosen case: common ones plus that case (all when none chosen). */
export function visibleItems(items: readonly ChecklistItem[], caseLabel: string) {
  return items.filter((item) => !item.case_label || !caseLabel || item.case_label === caseLabel);
}

/** `procedure_id` + optional `case_label` body (the API lists a case's documents only then). */
function caseBody(procedureId: string, caseLabel: string, received: string[]): IntakeCheckIn {
  const body: IntakeCheckIn = { procedure_id: procedureId, received };
  if (caseLabel) body.case_label = caseLabel;
  return body;
}

type OnOk = (out: IntakeCheckOut) => void;
type Send = (kind: Busy, body: IntakeCheckIn, onOk: OnOk, onFail?: () => void) => void;

/** Busy/error state of `/v1/coach/intake-check`; only the latest request may update the screen. */
function useIntakeRequest(client: ApiClient) {
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);
  const run = async (...[kind, body, onOk, onFail]: Parameters<Send>) => {
    const ticket = ++latest.current;
    setBusy(kind);
    setError(null);
    try {
      const out = await client.intakeCheck(body);
      if (ticket === latest.current) onOk(out);
    } catch (caught) {
      if (ticket !== latest.current) return;
      setError(caught instanceof ApiError ? caught.message : vi.errors.generic);
      onFail?.();
    } finally {
      if (ticket === latest.current) setBusy(null);
    }
  };
  const send: Send = (...args) => void run(...args);
  return { busy, error, setError, send };
}

/** Body of the final check: the ticked documents among those shown for the chosen case. */
function checkBody(lookup: IntakeCheckOut, caseLabel: string, received: ReadonlySet<string>) {
  const keys = visibleItems(lookup.items, caseLabel)
    .map((item) => item.doc_key)
    .filter((key) => received.has(key));
  return caseBody(lookup.procedure.procedure_id, caseLabel, keys);
}

/**
 * State of the intake desk. `chooseCase` re-asks the API for the chosen case: without
 * `case_label` it lists common documents only (none at all when every document belongs to a
 * case). Ticks are kept per document, so switching back and forth never loses what the officer
 * already marked. A by-id answer has no alternatives, so the ones from the search stay on
 * screen (no layout jump).
 */
function useIntake(client: ApiClient) {
  const { busy, error, setError, send: request } = useIntakeRequest(client);
  const [lookup, setLookup] = useState<IntakeCheckOut | null>(null);
  const [received, setReceived] = useState<ReadonlySet<string>>(() => new Set());
  const [caseLabel, setCaseLabel] = useState('');
  const [result, setResult] = useState<IntakeCheckOut | null>(null);
  const send: Send = (...args) => {
    setResult(null);
    request(...args);
  };
  const load = (body: IntakeCheckIn) =>
    send('search', body, (out) => {
      setLookup(out);
      setReceived(new Set());
      setCaseLabel('');
    });
  const search = (raw: string) => {
    const query = raw.trim();
    if (query.length < MIN_QUERY_CHARS) return setError(vi.officer.shortQuery);
    load({ query, received: [] });
  };
  const choose = (procedureId: string) => load({ procedure_id: procedureId, received: [] });
  const check = () => {
    if (!lookup) return;
    if (lookup.needs_case && !caseLabel) return setError(vi.officer.needsCase);
    send('check', checkBody(lookup, caseLabel, received), setResult);
  };
  const toggle = (key: string) => {
    setReceived((prev) => toggleKey(prev, key));
    setResult(null);
  };
  const chooseCase = (label: string) => {
    if (!lookup) return;
    const previous = caseLabel;
    const { alternatives } = lookup;
    setCaseLabel(label);
    const body = caseBody(lookup.procedure.procedure_id, label, []);
    send(
      'case',
      body,
      (out) => setLookup({ ...out, alternatives }),
      () => setCaseLabel(previous),
    );
  };
  const state = { lookup, received, caseLabel, result, busy, error };
  return { ...state, search, choose, check, toggle, chooseCase };
}

type Intake = ReturnType<typeof useIntake>;

function SearchForm({ intake }: { intake: Intake }) {
  const inputId = useId();
  const [query, setQuery] = useState('');
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    intake.search(query);
  };
  return (
    <form onSubmit={onSubmit} aria-busy={intake.busy === 'search'} className="flex flex-col gap-md">
      <label htmlFor={inputId} className="text-lg font-bold text-den">
        {vi.officer.queryLabel}
      </label>
      <input
        id={inputId}
        data-testid="officer-query"
        value={query}
        maxLength={200}
        enterKeyHint="search"
        onChange={(event) => setQuery(event.target.value)}
        className={FIELD_CLASS}
      />
      <BigButton
        type="submit"
        data-testid="officer-search"
        label={vi.buttons.search}
        variant="xanh"
        disabled={intake.busy !== null}
      />
    </form>
  );
}

function Alternatives({ intake }: { intake: Intake }) {
  const alternatives = intake.lookup?.alternatives ?? [];
  if (alternatives.length === 0) return null;
  return (
    <div className="flex flex-col gap-sm">
      <p className="text-base font-semibold text-den">{vi.officer.alternatives}</p>
      {alternatives.map((alt) => (
        <BigButton
          key={alt.procedure_id}
          data-testid={`officer-alt-${alt.procedure_id}`}
          label={`${vi.officer.choose} ${alt.ten}`}
          variant="trang"
          disabled={intake.busy !== null}
          onClick={() => intake.choose(alt.procedure_id)}
        />
      ))}
    </div>
  );
}

function CaseSelect({ intake }: { intake: Intake }) {
  const selectId = useId();
  const cases = intake.lookup?.cases ?? [];
  if (cases.length === 0) return null;
  const optionLabels = caseOptionLabels(cases);
  return (
    <div className="flex flex-col gap-sm">
      <label htmlFor={selectId} className="text-lg font-bold text-den">
        {vi.officer.caseLabel}
      </label>
      <select
        id={selectId}
        data-testid="case-select"
        value={intake.caseLabel}
        onChange={(event) => intake.chooseCase(event.target.value)}
        className={FIELD_CLASS}
      >
        <option value="">{vi.officer.noCase}</option>
        {cases.map((label, i) => (
          <option key={label} value={label}>
            {optionLabels[i]}
          </option>
        ))}
      </select>
    </div>
  );
}

function Checklist({ intake }: { intake: Intake }) {
  const items = visibleItems(intake.lookup?.items ?? [], intake.caseLabel);
  const groups = groupDocuments(items);
  const showLegends = groups.length > 1 || groups[0]?.label !== null;
  const waitingForCase = Boolean(intake.lookup?.needs_case) && !intake.caseLabel;
  return (
    <div className="flex flex-col gap-md">
      <h3 className="text-lg font-bold text-den">{vi.officer.checklistHeading}</h3>
      {waitingForCase ? (
        <p data-testid="case-hint" className="text-base font-semibold text-den">
          {vi.officer.caseHint}
        </p>
      ) : null}
      {groups.map((group) => (
        <fieldset key={group.label ?? ''} className="flex flex-col gap-sm">
          {showLegends ? (
            <GroupLegend label={group.label} className="pb-xs text-base font-bold text-den" />
          ) : null}
          {group.items.map((item) => (
            <CheckItem
              key={item.doc_key}
              testId={`checklist-item-${item.doc_key}`}
              doc={item}
              checked={intake.received.has(item.doc_key)}
              onToggle={() => intake.toggle(item.doc_key)}
            />
          ))}
        </fieldset>
      ))}
    </div>
  );
}

function ProcedureBlock({ intake }: { intake: Intake }) {
  const headingId = useId();
  if (!intake.lookup) return null;
  const { procedure } = intake.lookup;
  return (
    <section
      data-testid="officer-procedure"
      aria-labelledby={headingId}
      className="flex flex-col gap-md rounded-2xl border-4 border-xam bg-trang p-md"
    >
      <h2 id={headingId} className="text-xl font-bold leading-snug text-xanh">
        {procedure.ten}
      </h2>
      {procedure.co_quan ? (
        <p className="text-base text-den">{`${vi.officer.agency} ${procedure.co_quan}`}</p>
      ) : null}
      <Alternatives intake={intake} />
      <CaseSelect intake={intake} />
      <Checklist intake={intake} />
      <BigButton
        data-testid="officer-check"
        label={vi.buttons.checkFile}
        variant="xanh"
        disabled={intake.busy !== null}
        onClick={intake.check}
      />
    </section>
  );
}

function useCopy(text: string) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const copy = async () => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(text);
      setState('copied');
    } catch {
      setState('failed');
    }
  };
  const note = { idle: '', copied: vi.officer.copied, failed: vi.officer.copyFailed }[state];
  return { copy, note };
}

/** One document of a result list: preview + "Xem đủ" when the official name is long. */
function DocLine({ item }: { item: ChecklistItem }) {
  const textId = useId();
  const name = useExpandable(item.name);
  return (
    <li className="flex flex-col gap-xs">
      <span id={textId}>{describeDoc(item, name.shown)}</span>
      <ExpandToggle state={name} controls={textId} />
    </li>
  );
}

/** Required documents not received; conditional ones are never "missing" (ADR-007 C6). */
function MissingList({ result }: { result: IntakeCheckOut }) {
  const missing = result.items.filter((item) => item.status === 'thieu' && !isConditional(item));
  if (result.missing_count === 0 || missing.length === 0) {
    return (
      <p data-testid="complete-note" className="text-lg font-bold text-xanh">
        {vi.officer.complete}
      </p>
    );
  }
  return (
    <div data-testid="missing-list" className="flex flex-col gap-sm text-do">
      <p className="text-lg font-bold">{`${vi.officer.missingPrefix} ${missing.length} ${vi.officer.missingSuffix}`}</p>
      <ul className="flex list-disc flex-col gap-sm pl-lg text-base font-semibold leading-snug">
        {missing.map((item) => (
          <DocLine key={item.doc_key} item={item} />
        ))}
      </ul>
    </div>
  );
}

/** Conditional documents not ticked: a question for the citizen, not a missing item. */
function ConditionalList({ result }: { result: IntakeCheckOut }) {
  const pending = result.items.filter((item) => isConditional(item) && item.status !== 'da_nhan');
  if (pending.length === 0) return null;
  return (
    <div data-testid="conditional-list" className="flex flex-col gap-sm text-den">
      <p className="text-lg font-bold">{vi.officer.conditionalHeading}</p>
      <ul className="flex list-disc flex-col gap-sm pl-lg text-base leading-snug">
        {pending.map((item) => (
          <DocLine key={item.doc_key} item={item} />
        ))}
      </ul>
    </div>
  );
}

function ResultSource({ result }: { result: IntakeCheckOut }) {
  const { procedure } = result;
  const origin = result.citations[0]?.source_portal || result.citations[0]?.agency;
  const fetchedOn = formatVnDate(procedure.fetched_at);
  return (
    <div className="flex flex-col gap-sm">
      {origin ? <p className="text-base text-den">{`${vi.source.from} ${origin}`}</p> : null}
      {fetchedOn ? (
        <p className="text-base text-den">{`${vi.source.fetchedOn} ${fetchedOn}`}</p>
      ) : null}
      {isSafeHttpsUrl(procedure.source_url) ? (
        <OfficialLink href={procedure.source_url} label={vi.officer.sourceLink} />
      ) : null}
    </div>
  );
}

function CheckResult({ result }: { result: IntakeCheckOut }) {
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { copy, note } = useCopy(result.message_for_citizen);
  useEffect(() => {
    const heading = headingRef.current;
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView?.({ block: 'start' });
  }, []);
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-md rounded-2xl border-4 border-xanh bg-trang p-md"
    >
      <h2
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        className="scroll-mt-md text-xl font-bold text-xanh"
      >
        {vi.buttons.checkFile}
      </h2>
      <MissingList result={result} />
      <ConditionalList result={result} />
      <div data-testid="citizen-message" className="flex flex-col gap-sm">
        <h3 className="text-lg font-bold text-den">{vi.officer.messageHeading}</h3>
        <p className="rounded-2xl border-4 border-xam p-md text-lg leading-snug text-den">
          {result.message_for_citizen}
        </p>
      </div>
      <BigButton
        data-testid="copy-message"
        label={vi.buttons.copyMessage}
        variant="trang"
        onClick={() => void copy()}
      />
      <p role="status" className="text-base font-semibold text-den">
        {note}
      </p>
      <ResultSource result={result} />
    </section>
  );
}

const BUSY_TEXT: Record<Exclude<Busy, null>, string> = {
  search: vi.officer.searching,
  case: vi.officer.loadingCase,
  check: vi.officer.checking,
};

function IntakeDesk({ client }: { client: ApiClient }) {
  const intake = useIntake(client);
  const busyText = intake.busy ? BUSY_TEXT[intake.busy] : '';
  return (
    <div className="flex flex-col gap-lg">
      <SearchForm intake={intake} />
      <p role="status" className="text-lg font-semibold text-den">
        {busyText}
      </p>
      {intake.error ? (
        <p
          role="alert"
          className="rounded-2xl border-4 border-do bg-trang p-md text-lg font-semibold text-do"
        >
          {intake.error}
        </p>
      ) : null}
      <ProcedureBlock key={intake.lookup?.procedure.procedure_id ?? ''} intake={intake} />
      {intake.result ? <CheckResult result={intake.result} /> : null}
    </div>
  );
}

export interface OfficerScreenProps {
  client: ApiClient;
}

export function OfficerScreen({ client }: OfficerScreenProps) {
  const { role } = useSession();
  const isStaff = role !== null && (STAFF_ROLES as readonly string[]).includes(role);
  return isStaff ? <IntakeDesk client={client} /> : <OfficerLogin client={client} />;
}
