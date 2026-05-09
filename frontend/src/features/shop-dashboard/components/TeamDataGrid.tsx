import React, { useMemo, useState } from "react";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { RotateCcw, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Employee {
  employee_link_id: number;
  shop_id: number;
  created_at: string;
  is_active: boolean;
  user: {
    id: number;
    username: string;
    email: string;
    role: string;
    is_active: boolean;
  };
}

interface TeamDataGridProps {
  rows: Employee[];
  onDelete: (id: number) => void;
  onReactivate: (id: number) => void;
}

export default function TeamDataGrid({ rows, onDelete, onReactivate }: TeamDataGridProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns = useMemo<ColumnDef<Employee>[]>(
    () => [
      { id: "id", header: "ID", accessorFn: (row) => row.user.id, meta: { align: "right" } },
      { id: "username", header: "Username", accessorFn: (row) => row.user.username },
      { id: "email", header: "Email", accessorFn: (row) => row.user.email },
      {
        id: "role",
        header: "Role",
        accessorFn: (row) => row.user.role.charAt(0).toUpperCase() + row.user.role.slice(1),
      },
      {
        id: "status",
        header: "Status",
        cell: ({ row }) => (
          <Badge variant={row.original.is_active ? "default" : "secondary"}>
            {row.original.is_active ? "Active" : "Inactive"}
          </Badge>
        ),
      },
      {
        accessorKey: "created_at",
        header: "Added On",
        cell: ({ getValue }) => new Date(String(getValue())).toLocaleDateString(),
      },
      {
        id: "actions",
        header: "Actions",
        cell: ({ row }) => {
          if (row.original.is_active) {
            return (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => onDelete(row.original.user.id)}
                aria-label={`Remove ${row.original.user.username}`}
              >
                <Trash2 className="text-destructive" />
              </Button>
            );
          }

          return (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => onReactivate(row.original.user.id)}
              aria-label={`Reactivate ${row.original.user.username}`}
            >
              <RotateCcw />
            </Button>
          );
        },
        enableSorting: false,
      },
    ],
    [onDelete, onReactivate],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    initialState: { pagination: { pageSize: 10 } },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId: (row) => String(row.user.id),
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-xl border bg-card">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  No team members found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
          Previous
        </Button>
        <Button variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
          Next
        </Button>
      </div>
    </div>
  );
}
