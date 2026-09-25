/** "Ứng dụng mô phỏng" badge — visible on every screen so nobody mistakes this for a real app. */
import { vi } from '../i18n/vi';

export function SimBadge() {
  return (
    <span
      data-testid="sim-badge"
      className="inline-block rounded-full bg-xam px-lg py-xs text-base font-bold text-trang"
    >
      {vi.simBadge}
    </span>
  );
}
