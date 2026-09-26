"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";
import { RosterAvatar } from "./roster-primitives";

/**
 * A staff/teacher roster avatar: the enrolled biometric face photo when we have
 * one, falling back to the initials bubble on a missing `src` or a load error
 * (e.g. a 404 for staff with no enrolled face). The image is a same-origin
 * `/api` request so the auth cookie rides along.
 */
export function FaceAvatar({
  src,
  first,
  last,
  className,
}: {
  src: string | null | undefined;
  first: string;
  last: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return <RosterAvatar first={first} last={last} className={className} />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- authed same-origin blob, not a static asset
    <img
      src={src}
      alt={`${first} ${last}`.trim()}
      onError={() => setFailed(true)}
      className={cn(
        "inline-block h-7 w-7 rounded-full bg-primary/10 object-cover",
        className,
      )}
    />
  );
}
