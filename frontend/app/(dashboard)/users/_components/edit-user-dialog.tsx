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
import type { AdminUser, RoleOption, UserUpdate } from "../_schemas/users";

const SELECT_CLASS =
  "h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

interface Props {
  user: AdminUser | null;
  roles: RoleOption[];
  onOpenChange: (open: boolean) => void;
  onSubmit: (id: string, data: UserUpdate) => Promise<void> | void;
  isPending: boolean;
}

export function EditUserDialog({ user, roles, onOpenChange, onSubmit, isPending }: Props) {
  return (
    <Dialog open={!!user} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Edit user</DialogTitle>
        <DialogDescription>{user?.email}</DialogDescription>
        {/* Keyed by user id so each target mounts a fresh form (no effect sync). */}
        {user && (
          <EditForm
            key={user.id}
            user={user}
            roles={roles}
            isPending={isPending}
            onSubmit={onSubmit}
            onDone={() => onOpenChange(false)}
          />
        )}
      </DialogPopup>
    </Dialog>
  );
}

function EditForm({
  user, roles, isPending, onSubmit, onDone,
}: {
  user: AdminUser;
  roles: RoleOption[];
  isPending: boolean;
  onSubmit: (id: string, data: UserUpdate) => Promise<void> | void;
  onDone: () => void;
}) {
  const [form, setForm] = useState({
    first_name: user.first_name,
    last_name: user.last_name,
    phone: user.phone ?? "",
    role: user.roles[0] ?? "",
    status: user.status,
  });
  const [error, setError] = useState("");

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await onSubmit(user.id, {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim() || null,
        role: form.role || undefined,
        status: form.status,
      });
      onDone();
    } catch (err) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ?? "Failed to update user";
      setError(message);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="e-first">First name</Label>
          <Input id="e-first" required value={form.first_name}
            onChange={(e) => set("first_name", e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="e-last">Last name</Label>
          <Input id="e-last" required value={form.last_name}
            onChange={(e) => set("last_name", e.target.value)} />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="e-phone">Phone (optional)</Label>
        <Input id="e-phone" value={form.phone}
          onChange={(e) => set("phone", e.target.value)} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="e-role">Role</Label>
          <select id="e-role" className={SELECT_CLASS} value={form.role}
            onChange={(e) => set("role", e.target.value)}>
            {roles.map((r) => (
              <option key={r.name} value={r.name}>{r.display_name}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="e-status">Status</Label>
          <select id="e-status" className={SELECT_CLASS} value={form.status}
            onChange={(e) => set("status", e.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="mt-2 flex justify-end gap-2">
        <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
        <Button type="submit" disabled={isPending}>
          {isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
