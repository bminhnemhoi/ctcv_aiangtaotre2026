/**
 * One answer of the coach: big text, the green "Nguồn" button (invariant 3), the document
 * card, an honest "not sure" box when escalating (no fake "volunteer notified" button — there
 * is no queue yet) and a warning box when the question was refused.
 */
import { useEffect, useId, useRef, useState } from 'react';
import type { AskOut } from '../api/types';
import { BigButton } from '../components/BigButton';
import { vi } from '../i18n/vi';
import { DocumentsCard } from './DocumentsCard';
import { SourcePanel } from './SourcePanel';

export interface AnswerCardProps {
  answer: AskOut;
}

function AnswerText({ text }: { text: string }) {
  return (
    <p data-testid="answer-text" className="text-lg font-semibold leading-snug text-den">
      {text}
    </p>
  );
}

function RefusedBox({ text }: { text: string }) {
  return (
    <div
      data-testid="refused-box"
      className="flex flex-col gap-sm rounded-2xl border-4 border-do bg-trang p-md"
    >
      <p className="text-lg font-bold text-do">{vi.answer.refusedHeading}</p>
      <AnswerText text={text} />
    </div>
  );
}

function EscalateBox() {
  return (
    <p
      data-testid="escalate-box"
      className="rounded-2xl border-4 border-den bg-vang p-md text-lg font-bold leading-snug text-den"
    >
      {vi.answer.escalate}
    </p>
  );
}

function Sources({ answer }: AnswerCardProps) {
  const panelId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  // Bring the button and the opened panel above the fixed footer.
  useEffect(() => {
    if (open) wrapRef.current?.scrollIntoView?.({ block: 'start' });
  }, [open]);

  if (answer.citations.length === 0) return null;
  return (
    <div ref={wrapRef} className="flex scroll-mt-md flex-col gap-md">
      <BigButton
        data-testid="btn-nguon"
        label={vi.buttons.source}
        variant="xanh"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      />
      {open ? <SourcePanel id={panelId} citations={answer.citations} /> : null}
    </div>
  );
}

export function AnswerCard({ answer }: AnswerCardProps) {
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const documents = answer.procedure?.documents ?? [];

  // A new answer takes the focus (screen readers announce it) and scrolls to the top: plain
  // focus would not scroll when the heading sits in the viewport but behind the fixed footer.
  useEffect(() => {
    const heading = headingRef.current;
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView?.({ block: 'start' });
  }, []);

  return (
    <div
      data-testid="answer"
      data-reason={answer.reason}
      data-mode={answer.answer_mode}
      className="flex flex-col gap-lg"
    >
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
          {vi.answer.heading}
        </h2>
        {answer.refused ? <RefusedBox text={answer.answer} /> : <AnswerText text={answer.answer} />}
        {answer.escalate ? <EscalateBox /> : null}
        <p className="text-base text-den">{vi.answer.aiLabel}</p>
        <Sources answer={answer} />
      </section>
      {answer.procedure && documents.length > 0 ? (
        <DocumentsCard procedure={answer.procedure} />
      ) : null}
    </div>
  );
}
