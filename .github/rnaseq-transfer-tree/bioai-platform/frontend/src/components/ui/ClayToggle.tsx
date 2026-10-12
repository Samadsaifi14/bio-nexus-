'use client';

/**
 * Claymorphism switch — for discrete, low-stakes, single-purpose choices
 * (e.g. implicit vs explicit solvent, show/hide overlays).
 *
 * Signal: "this is a tactile, pressable object, not data."
 * Never use this for critical actions (Run/Submit/Delete) — see CriticalButton.
 */

interface ClayToggleProps {
  checked: boolean;
  onChange: (value: boolean) => void;
  label?: string;
  hint?: string;
  disabled?: boolean;
  className?: string;
}

export function ClayToggle({
  checked,
  onChange,
  label,
  hint,
  disabled,
  className = '',
}: ClayToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`group flex items-center gap-3 text-left disabled:opacity-40 ${className}`}
    >
      <span
        className="clay-toggle-track relative h-6 w-11 shrink-0 rounded-full transition-colors"
        style={{
          background: checked
            ? 'rgba(74,222,128,0.18)'
            : 'linear-gradient(145deg, #181830 0%, #0D0D1A 100%)',
        }}
      >
        <span
          className="clay-toggle-thumb absolute top-[2px] h-5 w-5 rounded-full transition-[left] duration-200"
          style={{ left: checked ? 'calc(100% - 1.375rem)' : '0.125rem' }}
        />
      </span>

      {(label || hint) && (
        <span className="flex flex-col">
          {label && <span className="text-sm text-text-primary">{label}</span>}
          {hint && <span className="text-[11px] text-text-muted">{hint}</span>}
        </span>
      )}
    </button>
  );
}
