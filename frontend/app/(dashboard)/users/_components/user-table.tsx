"use client";

import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import type { AdminUser } from "../_schemas/users";

interface Props {
  users: AdminUser[];
  roleLabels: Record<string, string>;
  currentUserId: string | undefined;
  onEdit: (u: AdminUser) => void;
  onResetPassword: (u: AdminUser) => void;
  onDelete: (u: AdminUser) => void;
}

export function UserTable({
  users, roleLabels, currentUserId, onEdit, onResetPassword, onDelete,
}: Props) {
  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead className="hidden sm:table-cell">Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((u) => {
            const isSelf = u.id === currentUserId;
            return (
              <TableRow key={u.id}>
                <TableCell>
                  <div className="flex flex-col gap-0.5">
                    <span className="font-medium">
                      {`${u.first_name} ${u.last_name}`.trim() || "—"}
                      {isSelf && (
                        <span className="ml-1.5 text-xs text-muted-foreground">(you)</span>
                      )}
                    </span>
                    <span className="text-xs text-muted-foreground sm:hidden">
                      {u.email}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                  {u.email}
                </TableCell>
                <TableCell className="text-sm">
                  {u.roles.map((r) => roleLabels[r] ?? r).join(", ") || "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={u.status === "active" ? "success" : "destructive"}>
                    {u.status === "active" ? "Active" : "Inactive"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      render={<Button variant="outline" size="sm">Manage</Button>}
                    />
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => onEdit(u)}>
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onResetPassword(u)}>
                        Reset password
                      </DropdownMenuItem>
                      {!isSelf && (
                        <DropdownMenuItem onClick={() => onDelete(u)}>
                          Delete
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
