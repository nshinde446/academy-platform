import Link from "next/link";

import { ErrorState } from "@/components/ui/error-state";
import { Button } from "@/components/ui/button";

/** 404 for any unmatched route. Rendered inside the root layout. */
export default function NotFound() {
  return (
    <ErrorState
      title="Page not found"
      description="That link doesn't point anywhere in the app. It may have been renamed, or the record it referred to was deleted."
      action={
        <Button render={<Link href="/home" />}>Back to dashboard</Button>
      }
    />
  );
}
