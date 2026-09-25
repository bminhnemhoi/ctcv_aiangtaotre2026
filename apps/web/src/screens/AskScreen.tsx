/**
 * "Hỏi thủ tục" (ADR-007 C7): one text box, one green "Hỏi" button, three example questions
 * and the cited answer. Needs a class token (from the class QR, `?lop=`) — without it the
 * screen only invites the learner to scan the code. Questions are not stored anywhere here.
 */
import { useId, useRef, useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react';
import { ApiError, type ApiClient } from '../api/client';
import type { AskOut } from '../api/types';
import { BigButton } from '../components/BigButton';
import { RepeatIcon } from '../components/icons';
import { vi } from '../i18n/vi';
import { useSession } from '../state/session';
import { AnswerCard } from './AnswerCard';

/** Maximum question length accepted by `/v1/coach/ask`. */
export const MAX_QUESTION_CHARS = 500;

/** Join lines and squeeze spaces: the API treats multi-line text as pasted content. */
export function normalizeQuestion(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

export interface JoinStatus {
  pending: boolean;
  error?: string | null;
}

export interface AskScreenProps {
  client: ApiClient;
  joinStatus?: JoinStatus;
}

type AskState =
  | { kind: 'idle' }
  | { kind: 'empty' }
  | { kind: 'repeat' }
  | { kind: 'pending' }
  | { kind: 'error'; message: string }
  | { kind: 'answered'; answer: AskOut; id: number };

const STATUS_TEXT: Partial<Record<AskState['kind'], string>> = {
  empty: vi.ask.empty,
  repeat: vi.subtitle.repeat,
  pending: vi.ask.waiting,
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : vi.errors.generic;
}

function RepeatButton({ onClick }: { onClick: () => void }) {
  return (
    <BigButton
      data-testid="btn-repeat"
      label={vi.buttons.repeat}
      icon={<RepeatIcon />}
      variant="trang"
      onClick={onClick}
    />
  );
}

function ErrorLine({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-2xl border-4 border-do bg-trang p-md text-lg font-semibold text-do"
    >
      {message}
    </p>
  );
}

function NeedClass({ joinStatus }: { joinStatus?: JoinStatus }) {
  const [repeats, setRepeats] = useState(0);
  return (
    <div className="flex flex-col gap-lg">
      <p
        key={repeats}
        role="status"
        className="rounded-2xl border-4 border-xam bg-trang p-lg text-lg font-semibold leading-snug text-den"
      >
        {joinStatus?.pending ? vi.ask.joining : vi.ask.needClass}
      </p>
      {joinStatus?.error ? <ErrorLine message={joinStatus.error} /> : null}
      <RepeatButton onClick={() => setRepeats((n) => n + 1)} />
    </div>
  );
}

function ExampleChips({ onPick }: { onPick: (text: string) => void }) {
  return (
    <section aria-labelledby="ask-examples-label" className="flex flex-col gap-sm">
      <p id="ask-examples-label" className="text-base font-semibold text-den">
        {vi.ask.examplesLabel}
      </p>
      {vi.ask.examples.map((text, index) => (
        <button
          key={text}
          type="button"
          data-testid={`example-chip-${index + 1}`}
          onClick={() => onPick(text)}
          className="min-h-tap w-full rounded-2xl border-4 border-xanh bg-trang px-md py-sm text-left text-base font-semibold leading-snug text-xanh active:scale-95"
        >
          {text}
        </button>
      ))}
    </section>
  );
}

function useAsk(client: ApiClient) {
  const [state, setState] = useState<AskState>({ kind: 'idle' });
  const seq = useRef(0);

  const send = async (raw: string): Promise<boolean> => {
    const question = normalizeQuestion(raw).slice(0, MAX_QUESTION_CHARS);
    if (!question) {
      setState({ kind: 'empty' });
      return false;
    }
    const id = ++seq.current;
    setState({ kind: 'pending' });
    try {
      const answer = await client.ask(question);
      if (id === seq.current) setState({ kind: 'answered', answer, id });
    } catch (error) {
      if (id === seq.current) setState({ kind: 'error', message: errorMessage(error) });
    }
    return true;
  };

  const reset = () => {
    seq.current += 1;
    setState({ kind: 'repeat' });
  };

  return { state, send, reset };
}

interface QuestionFormProps {
  inputRef: RefObject<HTMLTextAreaElement>;
  text: string;
  pending: boolean;
  onText: (text: string) => void;
  onSend: () => void;
  onRepeat: () => void;
}

/** The question box, the green "Hỏi" button and "Nói lại". Enter sends; Shift+Enter breaks. */
function QuestionForm({ inputRef, text, pending, onText, onSend, onRepeat }: QuestionFormProps) {
  const inputId = useId();
  const privacyId = useId();
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSend();
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    onSend();
  };
  return (
    <form onSubmit={onSubmit} aria-busy={pending} className="flex flex-col gap-md">
      <label htmlFor={inputId} className="text-xl font-bold leading-snug text-den">
        {vi.ask.label}
      </label>
      <textarea
        id={inputId}
        ref={inputRef}
        data-testid="ask-input"
        value={text}
        rows={3}
        maxLength={MAX_QUESTION_CHARS}
        enterKeyHint="send"
        aria-describedby={privacyId}
        onChange={(event) => onText(event.target.value)}
        onKeyDown={onKeyDown}
        className="min-h-[7.5rem] w-full resize-y rounded-2xl border-4 border-xam bg-trang p-md text-lg leading-snug text-den"
      />
      <p id={privacyId} className="text-base text-den">
        {vi.ask.privacy}
      </p>
      <BigButton
        type="submit"
        data-testid="ask-submit"
        label={vi.buttons.ask}
        variant="xanh"
        disabled={pending}
      />
      <RepeatButton onClick={onRepeat} />
    </form>
  );
}

/** Live status line (always in the page so screen readers hear every change). */
function StatusLine({ text }: { text: string }) {
  return (
    <p
      role="status"
      className={
        text
          ? 'rounded-2xl border-4 border-xam p-md text-lg font-semibold leading-snug text-den'
          : 'sr-only'
      }
    >
      {text}
    </p>
  );
}

function AskForm({ client }: { client: ApiClient }) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState('');
  const { state, send, reset } = useAsk(client);
  const pending = state.kind === 'pending';

  const submit = (value: string) => {
    if (pending) return;
    void send(value).then((sent) => {
      if (!sent) inputRef.current?.focus();
    });
  };
  const onRepeat = () => {
    setText('');
    reset();
    inputRef.current?.focus();
  };
  const onPick = (example: string) => {
    setText(example);
    submit(example);
  };

  return (
    <div className="flex flex-col gap-lg">
      <QuestionForm
        inputRef={inputRef}
        text={text}
        pending={pending}
        onText={setText}
        onSend={() => submit(text)}
        onRepeat={onRepeat}
      />
      <StatusLine text={STATUS_TEXT[state.kind] ?? ''} />
      {state.kind === 'error' ? <ErrorLine message={state.message} /> : null}
      {state.kind === 'answered' ? <AnswerCard key={state.id} answer={state.answer} /> : null}
      {state.kind !== 'answered' && !pending ? <ExampleChips onPick={onPick} /> : null}
    </div>
  );
}

export function AskScreen({ client, joinStatus }: AskScreenProps) {
  const session = useSession();
  if (!session.token) return <NeedClass joinStatus={joinStatus} />;
  return <AskForm client={client} />;
}
