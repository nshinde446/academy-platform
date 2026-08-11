"use client";

import { useState } from "react";

/**
 * The student's enrolled face photo (from the biometric backup) as a round
 * avatar, falling back to their initials when we have no photo. The image is a
 * same-origin `/api` request so the auth cookie rides along; a 404 (no photo)
 * flips to the initials fallback via onError.
 */
export function StudentAvatar({
  studentId,
  name,
  size = 64,
}: {
  studentId: string;
  name: string;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  const initials =
    name
      .trim()
      .split(/\s+/)
      .map((w) => w[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?";
  const base =
    "shrink-0 rounded-full bg-muted object-cover ring-1 ring-foreground/10";
  const style = { width: size, height: size };

  if (failed) {
    return (
      <div
        style={style}
        className={`${base} flex items-center justify-center text-sm font-medium text-muted-foreground`}
        aria-label={name}
      >
        {initials}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- authed same-origin blob, not a static asset
    <img
      src={`/api/v1/attendance/provisioning/biometrics/${studentId}/photo`}
      alt={`${name} face`}
      style={style}
      className={base}
      onError={() => setFailed(true)}
    />
  );
}
