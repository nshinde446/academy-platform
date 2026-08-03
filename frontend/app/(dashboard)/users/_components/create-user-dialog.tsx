"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogTrigger,
  DialogPopup,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import type { RoleOption, UserCreate } from "../_schemas/users";

const SELECT_CLASS =
  "h-9 w-full rounded-lg border border-input bg-background px-3 text-sm";

interface Props {
  roles: RoleOption[];
  onSubmit: (data: UserCreate) => Promise<void> | void;
  isPending: boolean;
}

export function CreateUserDialog({ roles, onSubmit, isPending }: Props) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    phone: "",
    role: "",
    password: "",
  });
  const [error, setError] = useState("");

  // Reset on close via the handler (not an effect) so a reopen starts fresh.
  function handleOpenChange(next: boolean) {
    if (!next) {
      setForm({ email: "", first_name: "", last_name: "", phone: "", role: "", password: "" });
      setError("");
    }
    setOpen(next);
  }

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.role) {
      setError("Pick a role");
      return;
    }
    if (form.password.length < 8) {
      setError("Temporary password must be at least 8 characters");
      return;
    }
    try {
      await onSubmit({
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim() || null,
        role: form.role,
        password: form.password,
      });
      setOpen(false);
    } catch (err) {
      const message =
        (err as { response?: { data?: { error?: { message?: string } } } })
          ?.response?.data?.error?.message ?? "Failed to create user";
      setError(message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger render={<Button onClick={() => setOpen(true)}>Add user</Button>} />
      <DialogPopup>
        <DialogTitle>Add user</DialogTitle>
        <DialogDescription>
          Create a staff account. Share the temporary password — they can change
          it from their profile after signing in.
        </DialogDescription>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="u-first">First name</Label>
              <Input id="u-first" required value={form.first_name}
                onChange={(e) => set("first_name", e.target.value)} />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="u-last">Last name</Label>
              <Input id="u-last" required value={form.last_name}
                onChange={(e) => set("last_name", e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="u-email">Email</Label>
            <Input id="u-email" type="email" required value={form.email}
              onChange={(e) => set("email", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="u-phone">Phone (optional)</Label>
            <Input id="u-phone" value={form.phone}
              onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="u-role">Role</Label>
            <select id="u-role" className={SELECT_CLASS} required value={form.role}
              onChange={(e) => set("role", e.target.value)}>
              <option value="">Select a role…</option>
              {roles.map((r) => (
                <option key={r.name} value={r.name}>{r.display_name}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="u-pass">Temporary password</Label>
            <Input id="u-pass" type="text" required minLength={8} value={form.password}
              onChange={(e) => set("password", e.target.value)}
              placeholder="At least 8 characters" />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <DialogClose render={<Button type="button" variant="outline">Cancel</Button>} />
            <Button type="submit" disabled={isPending}>
              {isPending ? "Creating…" : "Create user"}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  );
}
