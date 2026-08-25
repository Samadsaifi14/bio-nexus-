import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';

/**
 * Consume a one-shot sessionStorage pre-fill param.
 * Reads the value and immediately removes it so it can't be re-used on refresh.
 */
export function consumeParam(key: string): string | null {
  if (typeof window === 'undefined') return null;
  const v = sessionStorage.getItem(key);
  if (v !== null) sessionStorage.removeItem(key);
  return v;
}

/**
 * Set a pre-fill param in sessionStorage and navigate to the target route.
 * The target page should call `consumeParam(key)` on mount.
 */
export function setPrefill(
  router: AppRouterInstance,
  key: string,
  value: string,
  target: string,
) {
  sessionStorage.setItem(key, value);
  router.push(target);
}
