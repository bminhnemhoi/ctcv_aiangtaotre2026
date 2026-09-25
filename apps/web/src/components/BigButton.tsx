/**
 * The only kind of button in the app: at least `MIN_TAP_PX` tall, icon + text, one of the
 * named colours so the coach can say "bấm nút màu xanh có chữ …".
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';

/** Background colour name (see src/theme/tokens.ts `contrastPairs`). */
export type BigButtonVariant = 'xanh' | 'do' | 'vang' | 'trang';

const VARIANT_CLASSES: Record<BigButtonVariant, string> = {
  xanh: 'bg-xanh text-trang border-xanh',
  do: 'bg-do text-trang border-do',
  vang: 'bg-vang text-den border-den',
  trang: 'bg-trang text-xanh border-xanh',
};

export interface BigButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> {
  /** Visible text (always present — icons alone are never enough). */
  label: string;
  icon?: ReactNode;
  variant?: BigButtonVariant;
}

export function BigButton({
  label,
  icon,
  variant = 'xanh',
  className = '',
  type = 'button',
  ...rest
}: BigButtonProps) {
  return (
    <button
      type={type}
      data-variant={variant}
      className={`flex min-h-tap w-full min-w-tap items-center justify-center gap-sm rounded-2xl border-4 px-lg py-sm text-lg font-bold leading-tight shadow-sm active:scale-95 ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {icon ? (
        <span aria-hidden="true" className="shrink-0 leading-none">
          {icon}
        </span>
      ) : null}
      <span>{label}</span>
    </button>
  );
}
