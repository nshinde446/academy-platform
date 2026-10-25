import type { ComponentType } from "react";

// A consistent "arriving soon" panel for portal sections whose content lands in
// a later slice. Keeps the shell fully navigable without faking data.
export function PortalPlaceholder({
  title,
  description,
  icon: Icon,
}: {
  title: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold leading-tight">{title}</h1>
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card px-6 py-16 text-center">
        <div className="grid h-12 w-12 place-items-center rounded-full bg-muted">
          <Icon className="h-6 w-6 text-muted-foreground" />
        </div>
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
        <span className="rounded-full border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          Coming soon
        </span>
      </div>
    </div>
  );
}
