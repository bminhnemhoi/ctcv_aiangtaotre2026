/**
 * App shell and hash routes (ADR-007 C7):
 * - home: the E01 voice screen (mic, "Nói lại", always-visible "Gọi tình nguyện viên") plus the
 *   "Hỏi thủ tục" entry;
 * - `#hoi-thu-tuc`: cited answers about administrative procedures (citizen, class token);
 * - `#can-bo`: one-stop intake check (staff login).
 * Opening the class QR link (`?lop=<code>`) joins the class once; the token stays in memory.
 */
import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import { ApiError, api, type ApiClient } from './api/client';
import { BigButton } from './components/BigButton';
import { PhoneIcon } from './components/icons';
import { SimBadge } from './components/SimBadge';
import { Subtitle } from './components/Subtitle';
import { VoiceBar } from './components/VoiceBar';
import { useHashRoute, type Route } from './hooks/useHashRoute';
import { vi } from './i18n/vi';
import { AskScreen, type JoinStatus } from './screens/AskScreen';
import { OfficerScreen } from './screens/OfficerScreen';
import { startSession } from './state/session';

/** Query parameter carried by the class QR code. */
const CLASS_PARAM = 'lop';

type HeadingRef = RefObject<HTMLHeadingElement>;

interface ShellProps {
  title: string;
  headingRef: HeadingRef;
  /**
   * The "Gọi tình nguyện viên" bar. It is sticky, not fixed: it stays at the bottom of the
   * screen while scrolling but keeps its own place at the end of the page, so however tall it
   * grows (button on two lines, note above it, large system font) it never hides the last
   * content — no guessed bottom padding.
   */
  footer?: ReactNode;
  children: ReactNode;
}

function Shell({ title, headingRef, footer, children }: ShellProps) {
  const bottom = footer ? '' : 'pb-lg';
  return (
    <div className={`mx-auto flex min-h-dvh w-full max-w-screen-sm flex-col px-md ${bottom}`}>
      <header className="flex flex-col items-center gap-sm pt-md text-center">
        <SimBadge />
        <h1 ref={headingRef} tabIndex={-1} className="text-xl font-bold leading-tight text-xanh">
          {title}
        </h1>
      </header>
      <main className="flex flex-1 flex-col gap-md py-md">{children}</main>
      {footer}
    </div>
  );
}

interface CallFooterProps {
  onCall: () => void;
  /** When defined, a live note sits above the button (empty until the button is pressed). */
  note?: string;
}

function CallFooter({ onCall, note }: CallFooterProps) {
  return (
    <footer className="sticky bottom-0 -mx-md border-t-4 border-xam bg-trang p-md">
      <div className="flex w-full flex-col gap-sm">
        {note !== undefined ? (
          <p
            data-testid="volunteer-note"
            role="status"
            className="text-base font-semibold leading-snug text-den"
          >
            {note}
          </p>
        ) : null}
        <BigButton
          data-testid="btn-call"
          label={vi.buttons.callVolunteer}
          icon={<PhoneIcon />}
          variant="vang"
          onClick={onCall}
        />
      </div>
    </footer>
  );
}

function HomeScreen({ headingRef, onAsk }: { headingRef: HeadingRef; onAsk: () => void }) {
  const [listening, setListening] = useState(false);
  const [subtitle, setSubtitle] = useState<string>(vi.subtitle.idle);

  const say = (text: string, keepListening = false) => {
    setListening(keepListening);
    setSubtitle(text);
  };
  const handleSpeak = () => say(listening ? vi.subtitle.idle : vi.subtitle.listening, !listening);

  return (
    <Shell
      title={vi.appName}
      headingRef={headingRef}
      footer={<CallFooter onCall={() => say(vi.subtitle.volunteer)} />}
    >
      <Subtitle text={subtitle} />
      <VoiceBar
        listening={listening}
        onSpeak={handleSpeak}
        onRepeat={() => say(vi.subtitle.repeat)}
      />
      <BigButton
        data-testid="hoi-thu-tuc-button"
        label={vi.buttons.askProcedure}
        variant="trang"
        onClick={onAsk}
      />
    </Shell>
  );
}

interface AskRouteProps {
  client: ApiClient;
  headingRef: HeadingRef;
  joinStatus: JoinStatus;
}

function AskRoute({ client, headingRef, joinStatus }: AskRouteProps) {
  const [note, setNote] = useState('');
  return (
    <Shell
      title={vi.ask.title}
      headingRef={headingRef}
      footer={<CallFooter note={note} onCall={() => setNote(vi.subtitle.volunteer)} />}
    >
      <AskScreen client={client} joinStatus={joinStatus} />
    </Shell>
  );
}

function dropClassCodeFromUrl(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete(CLASS_PARAM);
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`);
}

/** Join the class named by `?lop=` exactly once, then remove the code from the address bar. */
function useClassJoin(client: ApiClient): JoinStatus {
  const started = useRef(false);
  const [status, setStatus] = useState<JoinStatus>({ pending: false });

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = new URLSearchParams(window.location.search).get(CLASS_PARAM)?.trim();
    if (!code) return;
    setStatus({ pending: true });
    client.join(code, vi.ask.learnerName).then(
      (auth) => {
        startSession(auth);
        dropClassCodeFromUrl();
        setStatus({ pending: false });
      },
      (error: unknown) => {
        const message = error instanceof ApiError ? error.message : vi.errors.generic;
        setStatus({ pending: false, error: message });
      },
    );
  }, [client]);

  return status;
}

/** Move focus to the new screen title when the route changes (not on first load). */
function useFocusOnRouteChange(route: Route, headingRef: HeadingRef): void {
  const previous = useRef(route);
  useEffect(() => {
    if (previous.current === route) return;
    previous.current = route;
    headingRef.current?.focus();
  }, [route, headingRef]);
}

export interface AppProps {
  /** Injectable for tests; defaults to the shared client. */
  client?: ApiClient;
}

export default function App({ client = api }: AppProps) {
  const [route, navigate] = useHashRoute();
  const joinStatus = useClassJoin(client);
  const headingRef = useRef<HTMLHeadingElement>(null);
  useFocusOnRouteChange(route, headingRef);

  if (route === 'hoi-thu-tuc') {
    return <AskRoute client={client} headingRef={headingRef} joinStatus={joinStatus} />;
  }
  if (route === 'can-bo') {
    return (
      <Shell title={vi.officer.title} headingRef={headingRef}>
        <OfficerScreen client={client} />
      </Shell>
    );
  }
  return <HomeScreen headingRef={headingRef} onAsk={() => navigate('hoi-thu-tuc')} />;
}
