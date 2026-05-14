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
import { RotateCcw, Search, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [filter, setFilter] = useState("");

  const filteredRows = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      [
        row.user.username,
        row.user.email,
        row.user.role,
        row.is_active ? "active" : "inactive",
        String(row.user.id),
      ]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [filter, rows]);

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
    data: filteredRows,
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
    <div className="rounded-2xl border border-border bg-card p-4 shadow-none">
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight text-foreground">Team roster</h2>
          <p className="mt-1 text-sm text-muted-foreground">Review employee access, status, and roles.</p>
        </div>
        <div className="relative w-full md:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search team..."
            className="h-10 rounded-xl border-border bg-background pl-9 shadow-none"
          />
        </div>
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-background">
        <Table>
          <TableHeader className="bg-muted/35">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} className="h-11 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
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
                <TableRow key={row.id} className="hover:bg-muted/35">
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
      <div className="mt-4 flex justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl border-border bg-background shadow-none"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl border-border bg-background shadow-none"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
