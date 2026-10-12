import { AxiosError } from 'axios';

export function extractErrorMessage(err: unknown, fallback = 'Request failed'): string {
  if (err instanceof AxiosError) {
    const detail = err.response?.data;
    if (detail && typeof detail === 'object' && 'detail' in detail && typeof detail.detail === 'string') {
      return detail.detail;
    }
    return err.message || fallback;
  }
  if (err instanceof Error) {
    return err.message || fallback;
  }
  return fallback;
}

export function extractErrorStatus(err: unknown): number | undefined {
  if (err instanceof AxiosError) {
    return err.response?.status;
  }
  return undefined;
}
