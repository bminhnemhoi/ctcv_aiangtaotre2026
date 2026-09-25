/** Big-print caption area: what the coach just said or what the app is doing. */
export interface SubtitleProps {
  text: string;
}

export function Subtitle({ text }: SubtitleProps) {
  return (
    <p
      data-testid="subtitle"
      role="status"
      aria-live="polite"
      className="min-h-[7rem] rounded-2xl border-4 border-xam bg-trang p-lg text-lg font-semibold leading-snug text-den"
    >
      {text}
    </p>
  );
}
