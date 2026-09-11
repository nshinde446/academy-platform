// Pull the human-readable message out of the backend's error envelope
// ({ error: { message } }) without reaching for `any`.
export function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { error?: { message?: string } } } })
    ?.response?.data?.error?.message;
  return data || fallback;
}
