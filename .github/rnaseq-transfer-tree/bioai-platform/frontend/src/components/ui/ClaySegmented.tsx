'use client';

/**
 * Claymorphism segmented control — a discrete picker between 2–4 modes
 * (e.g. rectangular/circular tree layout). Low-stakes, tactile.
 */

interface ClaySegmentedProps<T extends string> {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export function ClaySegmented<T extends string>({
  options,
  value,
  onChange,
  disabled,
  className = '',
  size = 'md',
}: ClaySegmentedProps<T>) {
  return (
    <div className={`clay inline-flex rounded-lg p-0.5 gap-0.5 ${disabled ? 'opacity-50' : ''} ${className}`}>
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            disabled={disabled}
            className={`rounded-md capitalize font-medium transition-colors ${
              size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm'
            } ${
              active
                ? 'bg-accent-cyan/20 text-accent-cyan'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
