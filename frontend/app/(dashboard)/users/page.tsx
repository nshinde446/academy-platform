"use client";

import { useMemo, useState } from "react";
import { useUserStore } from "@/store/user-store";
import { PageHeader } from "@/components/layout/page-header";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  useAdminUsers,
  useRoleOptions,
  useCreateUser,
  useUpdateUser,
  useResetUserPassword,
  useDeleteUser,
} from "./_hooks/use-users";
import type { AdminUser } from "./_schemas/users";
import { UserTable } from "./_components/user-table";
import { CreateUserDialog } from "./_components/create-user-dialog";
import { EditUserDialog } from "./_components/edit-user-dialog";
import { ResetPasswordDialog } from "./_components/reset-password-dialog";

const ADMIN_ROLES = ["super_admin", "branch_admin"];

export default function UsersPage() {
  const user = useUserStore((s) => s.user);
  const userStatus = useUserStore((s) => s.status);
  const isAdmin = (user?.roles ?? []).some((r) => ADMIN_ROLES.includes(r));

  const toast = useToast();
  const [editTarget, setEditTarget] = useState<AdminUser | null>(null);
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);

  const usersQuery = useAdminUsers(isAdmin);
  const rolesQuery = useRoleOptions(isAdmin);
  const createMutation = useCreateUser();
  const updateMutation = useUpdateUser();
  const resetMutation = useResetUserPassword();
  const deleteMutation = useDeleteUser();

  const roles = useMemo(() => rolesQuery.data ?? [], [rolesQuery.data]);
  const roleLabels = useMemo(
    () => Object.fromEntries(roles.map((r) => [r.name, r.display_name])),
    [roles],
  );

  if (userStatus === "loading") {
    return <TableSkeleton rows={6} />;
  }

  if (!isAdmin) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title="Users" />
        <p className="text-sm text-muted-foreground">
          You don’t have permission to manage users. Ask a branch admin or super
          admin for access.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Users"
        description="Create and manage staff accounts and their roles. New users get a temporary password they change after signing in."
        actions={
          <CreateUserDialog
            roles={roles}
            isPending={createMutation.isPending}
            onSubmit={async (data) => {
              await createMutation.mutateAsync(data);
              toast.success("User created", `${data.first_name} can now sign in.`);
            }}
          />
        }
      />

      {usersQuery.isLoading ? (
        <TableSkeleton rows={6} />
      ) : usersQuery.isError ? (
        <p className="text-sm text-destructive">Failed to load users.</p>
      ) : (usersQuery.data ?? []).length === 0 ? (
        <p className="text-sm text-muted-foreground">No users yet.</p>
      ) : (
        <UserTable
          users={usersQuery.data ?? []}
          roleLabels={roleLabels}
          currentUserId={user?.id}
          onEdit={setEditTarget}
          onResetPassword={setResetTarget}
          onDelete={setDeleteTarget}
        />
      )}

      <EditUserDialog
        user={editTarget}
        roles={roles}
        isPending={updateMutation.isPending}
        onOpenChange={(open) => !open && setEditTarget(null)}
        onSubmit={async (id, data) => {
          await updateMutation.mutateAsync({ id, data });
          toast.success("User updated");
        }}
      />

      <ResetPasswordDialog
        user={resetTarget}
        isPending={resetMutation.isPending}
        onOpenChange={(open) => !open && setResetTarget(null)}
        onSubmit={async (id, password) => {
          await resetMutation.mutateAsync({ id, password });
          toast.success("Password reset", "Share the new temporary password.");
        }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Delete user"
        description={
          deleteTarget
            ? `Delete ${deleteTarget.first_name} ${deleteTarget.last_name}? They will be signed out and can no longer log in.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await deleteMutation.mutateAsync(deleteTarget.id);
            toast.success("User deleted");
            setDeleteTarget(null);
          } catch (err) {
            const message =
              (err as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Failed to delete user";
            toast.error("Could not delete", message);
          }
        }}
      />
    </div>
  );
}
