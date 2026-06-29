import type { ReactNode } from "react";
import { InfoHint } from "@/components/ui/info-hint";

// Compact, single-row page header. The global top bar already names the page,
// so this stays small: title + an optional ⓘ for the (formerly always-on)
// description, with actions inline on the right instead of a stacked block.
// `children` is an optional second row for view toggles / filters.
export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div className="flex min-w-0 items-center gap-2">
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {title}
          </h1>
          {description && <InfoHint text={description} />}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
      {children}
    </div>
  );
}
