import React, { useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { useShop } from "../../../contexts/ShopContext";
import api from "../../../services/api";

type VisitRow = {
  id: number;
  customer_name?: string;
  notes?: string;
  assigned_employee?: { username?: string };
  service_cost?: number;
  completed_at?: string;
  service_started_at?: string;
};

const formatDuration = (row: VisitRow) => {
  if (!row.service_started_at || !row.completed_at) return "-";

  const start = new Date(row.service_started_at).getTime();
  const end = new Date(row.completed_at).getTime();
  const minutes = Math.round((end - start) / 60000);

  return `${minutes} min`;
};

export default function RecentVisitsDataGrid() {
  const { shop } = useShop();
  const [rows, setRows] = useState<VisitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [sorting, setSorting] = useState<SortingState>([]);

  useEffect(() => {
    const fetchHistory = async () => {
      if (!shop) return;

      try {
        setLoading(true);
        const queuesRes = await api.get(`/queues/shop/${shop.id}/all`);
        const allQueues = queuesRes.data;

        let allItems: VisitRow[] = [];
        allQueues.forEach((queue: any) => {
          if (queue.queue_items) {
            const completed = queue.queue_items.filter((item: any) => item.status === "completed");
            allItems = [...allItems, ...completed];
          }
        });

        allItems.sort((a, b) => new Date(b.completed_at || 0).getTime() - new Date(a.completed_at || 0).getTime());
        setRows(allItems);
      } catch (err) {
        console.error("Failed to fetch visit history", err);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [shop]);

  const columns = useMemo<ColumnDef<VisitRow>[]>(
    () => [
      { accessorKey: "customer_name", header: "Customer", cell: ({ getValue }) => String(getValue() || "-") },
      { accessorKey: "notes", header: "Service", cell: ({ row }) => row.original.notes || "General Service" },
      { id: "servedBy", header: "Served By", accessorFn: (row) => row.assigned_employee?.username || "Shop Owner" },
      {
        id: "paid",
        header: "Paid",
        accessorFn: (row) => row.service_cost || 0,
        cell: ({ getValue }) => `$${Number(getValue() || 0).toFixed(2)}`,
        meta: { align: "right" },
      },
      {
        accessorKey: "completed_at",
        header: "Date",
        cell: ({ getValue }) => {
          const value = getValue<string | undefined>();
          return value ? new Date(value).toLocaleDateString() : "-";
        },
      },
      {
        id: "duration",
        header: "Duration",
        cell: ({ row }) => formatDuration(row.original),
      },
    ],
    [],
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
    getRowId: (row) => String(row.id),
  });

  if (loading) {
    return (
      <div className="flex flex-col gap-2 rounded-2xl border border-border bg-card p-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-2xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
        No recent visits found.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-none">
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
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-end gap-2">
        <Button className="rounded-xl border-border bg-card shadow-none" variant="outline" size="sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()}>
          Previous
        </Button>
        <Button className="rounded-xl border-border bg-card shadow-none" variant="outline" size="sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
          Next
        </Button>
      </div>
    </div>
  );
}
