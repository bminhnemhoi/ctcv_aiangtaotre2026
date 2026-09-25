/**
 * Voice is the default channel (idea §4): one big mic button, an animated wave while
 * listening, and "Nói lại" always within reach.
 */
import { BigButton } from './BigButton';
import { MicIcon, RepeatIcon } from './icons';
import { vi } from '../i18n/vi';

export interface VoiceBarProps {
  listening: boolean;
  onSpeak: () => void;
  onRepeat: () => void;
}

const WAVE_DELAYS = [
  '[animation-delay:0ms]',
  '[animation-delay:120ms]',
  '[animation-delay:240ms]',
  '[animation-delay:120ms]',
  '[animation-delay:0ms]',
];

export function VoiceWave({ active }: { active: boolean }) {
  return (
    <div
      data-testid="voice-wave"
      data-active={active}
      role="img"
      aria-label={active ? vi.voice.listeningLabel : vi.voice.idleLabel}
      className="flex h-xl items-center justify-center gap-xs"
    >
      {WAVE_DELAYS.map((delay, index) => (
        <span
          key={index}
          className={`h-full w-sm origin-center rounded-full ${active ? `voice-wave-bar bg-xanh ${delay}` : 'scale-y-[0.15] bg-xam'}`}
        />
      ))}
    </div>
  );
}

export function VoiceBar({ listening, onSpeak, onRepeat }: VoiceBarProps) {
  return (
    <section aria-label={vi.voice.sectionLabel} className="flex flex-col gap-md">
      <VoiceWave active={listening} />
      <BigButton
        data-testid="btn-speak"
        label={vi.buttons.speak}
        icon={<MicIcon />}
        variant="xanh"
        aria-pressed={listening}
        onClick={onSpeak}
      />
      <BigButton
        data-testid="btn-repeat"
        label={vi.buttons.repeat}
        icon={<RepeatIcon />}
        variant="trang"
        onClick={onRepeat}
      />
    </section>
  );
}
