"use client";

import { useMemo } from "react";
import { Toast } from "@base-ui/react/toast";
import { Check, AlertCircle, Info, X } from "lucide-react";
import { cn } from "@/lib/utils";

// Non-blocking notifications, built on the project's @base-ui/react primitive
// (same base as dialog / dropdown-menu — no extra dependency). Wrap the app in
// <Toast.Provider> and render <Toaster /> once; call useToast() from anywhere
// inside the provider.

export { Toast };

type ToastType = "success" | "error" | "info";

const TYPE_META: Record<
  ToastType,
  { accent: string; icon: typeof Check }
> = {
  success: { accent: "border-l-[var(--success)] text-[var(--success)]", icon: Check },
  error: { accent: "border-l-destructive text-destructive", icon: AlertCircle },
  info: { accent: "border-l-brand-navy text-brand-navy", icon: Info },
};

function ToastList() {
  const { toasts } = Toast.useToastManager();
  return (
    <>
      {toasts.map((t) => {
        const meta = TYPE_META[(t.type as ToastType) ?? "info"] ?? TYPE_META.info;
        const Icon = meta.icon;
        return (
          <Toast.Root
            key={t.id}
            toast={t}
            className={cn(
              "flex items-start gap-2.5 rounded-lg border border-l-4 bg-card px-3.5 py-3 text-card-foreground shadow-md ring-1 ring-foreground/5",
              "transition-all data-[ending-style]:opacity-0 data-[starting-style]:opacity-0",
              meta.accent,
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <Toast.Title className="text-[13px] font-semibold text-foreground" />
              <Toast.Description className="text-[12px] text-muted-foreground" />
            </div>
            <Toast.Close
              aria-label="Dismiss"
              className="shrink-0 rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </Toast.Close>
          </Toast.Root>
        );
      })}
    </>
  );
}

/** Mount once, inside <Toast.Provider>. Renders toasts bottom-right. */
export function Toaster() {
  return (
    <Toast.Portal>
      <Toast.Viewport className="fixed bottom-4 right-4 z-[60] flex w-[20rem] max-w-[calc(100vw-2rem)] flex-col gap-2">
        <ToastList />
      </Toast.Viewport>
    </Toast.Portal>
  );
}

/**
 * Fire a toast from any component inside <Toast.Provider>:
 *   const toast = useToast();
 *   toast.success("Saved", "Draft stored.");
 */
export function useToast() {
  const manager = Toast.useToastManager();
  return useMemo(
    () => ({
      success: (title: string, description?: string) =>
        manager.add({ title, description, type: "success" }),
      error: (title: string, description?: string) =>
        manager.add({ title, description, type: "error", timeout: 6000 }),
      info: (title: string, description?: string) =>
        manager.add({ title, description, type: "info" }),
    }),
    [manager],
  );
}
