"use client";

import { useState } from "react";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * A small single-field prompt dialog — the sanctioned replacement for
 * window.prompt (which is lint-forbidden). Resolves the typed value on confirm.
 */
export function PromptDialog({
  open,
  onOpenChange,
  title,
  description,
  label = "Reason",
  placeholder,
  required = false,
  confirmLabel = "Confirm",
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  label?: string;
  placeholder?: string;
  required?: boolean;
  confirmLabel?: string;
  onConfirm: (value: string) => Promise<void> | void;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (required && !value.trim()) return;
    setBusy(true);
    try {
      await onConfirm(value.trim());
      setValue("");
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) setValue("");
        onOpenChange(o);
      }}
    >
      <DialogPopup>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{description ?? label}</DialogDescription>
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="prompt-value">{label}</Label>
            <Input
              id="prompt-value"
              value={value}
              placeholder={placeholder}
              autoFocus
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={busy || (required && !value.trim())}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      </DialogPopup>
    </Dialog>
  );
}
