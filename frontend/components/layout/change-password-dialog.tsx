"use client";

import { useState } from "react";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Self-service password change — available to every signed-in user (e.g. after
// an admin hands out a temporary password). Calls the API directly so it stays
// independent of any route-private hook.
export function ChangePasswordDialog({ open, onOpenChange }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  // Reset on close via the handler (not an effect) so a reopen starts fresh.
  function handleOpenChange(next: boolean) {
    if (!next) {
      setCurrent("");
      setNext("");
      setConfirm("");
      setError("");
      setDone(false);
    }
    onOpenChange(next);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (next.length < 8) {
      setError("New password must be at least 8 characters");
      return;
    }
    if (next !== confirm) {
      setError("New passwords do not match");
      return;
    }
    setPending(true);
    try {
      await apiClient.post("/api/v1/auth/change-password", {
        current_password: current,
        new_password: next,
      });
      setDone(true);
    } catch (err) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ?? "Failed to change password";
      setError(message);
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogPopup>
        <DialogTitle>Change password</DialogTitle>
        <DialogDescription>
          Update the password for your account.
        </DialogDescription>
        {done ? (
          <div className="mt-4 flex flex-col gap-4">
            <p className="text-sm text-emerald-600 dark:text-emerald-400">
              Password changed successfully.
            </p>
            <div className="flex justify-end">
              <DialogClose render={<Button>Done</Button>} />
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-current">Current password</Label>
              <Input id="cp-current" type="password" required value={current}
                onChange={(e) => setCurrent(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-new">New password</Label>
              <Input id="cp-new" type="password" required minLength={8} value={next}
                onChange={(e) => setNext(e.target.value)}
                placeholder="At least 8 characters" />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="cp-confirm">Confirm new password</Label>
              <Input id="cp-confirm" type="password" required value={confirm}
                onChange={(e) => setConfirm(e.target.value)} />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="mt-2 flex justify-end gap-2">
              <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
              <Button type="submit" disabled={pending}>
                {pending ? "Changing…" : "Change password"}
              </Button>
            </div>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  );
}
