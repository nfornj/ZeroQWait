import React, { useMemo } from "react";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type TableFormatKind = "currency" | "delta" | "percent" | "number";

export interface DataTableColumnFormat {
  kind: TableFormatKind;
  currency?: string;
  decimals?: number;
  showSign?: boolean;
  compact?: boolean;
  basis?: "fraction" | "unit";
  upIsPositive?: boolean;
}

export interface DataTableColumn {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
  priority?: "primary" | "secondary";
  format?: DataTableColumnFormat;
}

export interface DataTableProps {
  columns: DataTableColumn[];
  data: Record<string, unknown>[];
  rowIdKey: string;
}

const compareValues = (left: unknown, right: unknown) => {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  if (typeof left === "number" && typeof right === "number") return left - right;

  return String(left).localeCompare(String(right), undefined, {
    numeric: true,
    sensitivity: "base",
  });
};

const formatValue = (value: unknown, format?: DataTableColumnFormat): string => {
  if (value == null || value === "") return "-";
  if (!format) return String(value);

  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num)) return String(value);

  const decimals = format.decimals ?? 0;

  if (format.kind === "currency") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: format.currency || "USD",
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(num);
  }

  if (format.kind === "percent") {
    const pct = format.basis === "unit" ? num : num * 100;
    const prefix = format.showSign && pct > 0 ? "+" : "";
    return `${prefix}${pct.toFixed(decimals)}%`;
  }

  if (format.kind === "delta") {
    const prefix = format.showSign && num > 0 ? "+" : "";
    return `${prefix}${num.toFixed(decimals)}`;
  }

  return new Intl.NumberFormat("en-US", {
    notation: format.compact ? "compact" : "standard",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(num);
};

const getCellColor = (value: unknown, format?: DataTableColumnFormat): string | undefined => {
  if (!format || (format.kind !== "delta" && format.kind !== "percent")) return undefined;

  const num = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(num) || num === 0) return undefined;

  const positive = format.upIsPositive === false ? num < 0 : num > 0;
  return positive ? "text-success" : "text-destructive";
};

const alignClass = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

const SortIcon = ({ direction }: { direction: false | "asc" | "desc" }) => {
  if (direction === "asc") return <ChevronUp className="size-3.5" />;
  if (direction === "desc") return <ChevronDown className="size-3.5" />;
  return <ChevronsUpDown className="size-3.5 opacity-40" />;
};

const DataTable: React.FC<DataTableProps> = ({ columns, data, rowIdKey }) => {
  const [sorting, setSorting] = React.useState<SortingState>([]);

  const tableColumns = useMemo<ColumnDef<Record<string, unknown>>[]>(
    () =>
      columns.map((column) => ({
        id: column.key,
        accessorKey: column.key,
        header: ({ column: tableColumn }) => (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className={cn(
              "h-8 px-2 text-xs font-semibold text-muted-foreground",
              column.align === "right" && "ml-auto",
              column.align === "center" && "mx-auto",
            )}
            onClick={() => tableColumn.toggleSorting(tableColumn.getIsSorted() === "asc")}
          >
            {column.label}
            <SortIcon direction={tableColumn.getIsSorted()} />
          </Button>
        ),
        cell: ({ getValue }) => {
          const value = getValue();

          return (
            <span className={getCellColor(value, column.format)}>
              {formatValue(value, column.format)}
            </span>
          );
        },
        sortingFn: (rowA, rowB) => compareValues(rowA.original[column.key], rowB.original[column.key]),
        meta: {
          align: column.align || "left",
          priority: column.priority,
        },
      })),
    [columns],
  );

  const table = useReactTable({
    data,
    columns: tableColumns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: (row, index) => String(row[rowIdKey] ?? index),
  });

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const align = header.column.columnDef.meta?.align || "left";

                return (
                  <TableHead key={header.id} className={cn("px-2", alignClass[align])}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => {
                  const align = cell.column.columnDef.meta?.align || "left";
                  const priority = cell.column.columnDef.meta?.priority;

                  return (
                    <TableCell
                      key={cell.id}
                      className={cn(
                        "text-foreground",
                        alignClass[align],
                        priority !== "primary" && "whitespace-nowrap",
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                No rows available.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};

export default DataTable;
