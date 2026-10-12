'use client';

import type { CSSProperties } from 'react';

/**
 * Claymorphism slider — for numeric, isolated, non-critical inputs
 * (MD run length, search hit count, bootstrap cutoff, etc.).
 */

interface ClaySliderProps {
  label?: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onChange: (value: number) => void;
  disabled?: boolean;
  className?: string;
}

export function ClaySlider({
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  onChange,
  disabled,
  className = '',
}: ClaySliderProps) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className={`flex flex-col gap-1.5 ${disabled ? 'opacity-40' : ''} ${className}`}>
      <div className="flex items-center justify-between">
        {label && <span className="text-sm text-text-primary">{label}</span>}
        <span className="font-mono text-xs text-accent-cyan">
          {value}
          {unit ? ` ${unit}` : ''}
        </span>
      </div>

      <input
        type="range"
        role="slider"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="clay-slider w-full"
        style={{ '--fill': `${pct}%` } as CSSProperties}
      />
    </div>
  );
}
