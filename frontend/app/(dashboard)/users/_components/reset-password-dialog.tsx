"use client";

import { useState } from "react";
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
import type { AdminUser } from "../_schemas/users";

interface Props {
  user: AdminUser | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (id: string, password: string) => Promise<void> | void;
  isPending: boolean;
}

export function ResetPasswordDialog({ user, onOpenChange, onSubmit, isPending }: Props) {
  return (
    <Dialog open={!!user} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Reset password</DialogTitle>
        <DialogDescription>
          Set a new temporary password for {user?.first_name} {user?.last_name}.
          This signs them out of any active sessions.
        </DialogDescription>
        {/* Keyed by user id so each target mounts a fresh form (no effect sync). */}
        {user && (
          <ResetForm
            key={user.id}
            user={user}
            isPending={isPending}
            onSubmit={onSubmit}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogPopup>
    </Dialog>
  );
}

function ResetForm({
  user, isPending, onSubmit, onDone,
}: {
  user: AdminUser;
  isPending: boolean;
  onSubmit: (id: string, password: string) => Promise<void> | void;
  onDone: () => void;
}) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    try {
      await onSubmit(user.id, password);
      onDone();
    } catch (err) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ?? "Failed to reset password";
      setError(message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <Label htmlFor="r-pass">New temporary password</Label>
        <Input id="r-pass" type="text" required minLength={8} value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters" />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="mt-2 flex justify-end gap-2">
        <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
        <Button type="submit" disabled={isPending}>
          {isPending ? "Resetting…" : "Reset password"}
        </Button>
      </div>
    </form>
  );
}
