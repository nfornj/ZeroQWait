import React, { useMemo, useState } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "../lib/utils";

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

type SortDirection = "asc" | "desc";

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
  return positive ? "text-emerald-400" : "text-red-400";
};

const alignClass = { left: "text-left", center: "text-center", right: "text-right" };

const DataTable: React.FC<DataTableProps> = ({ columns, data, rowIdKey }) => {
  const [sortKey, setSortKey] = useState<string>(columns[0]?.key || rowIdKey);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedRows = useMemo(() => {
    const rows = [...data];
    rows.sort((a, b) => {
      const result = compareValues(a[sortKey], b[sortKey]);
      return sortDirection === "asc" ? result : -result;
    });
    return rows;
  }, [data, sortDirection, sortKey]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  const SortIcon = ({ columnKey }: { columnKey: string }) => {
    if (sortKey !== columnKey) return <ChevronsUpDown className="ml-1 h-3 w-3 opacity-40" />;
    return sortDirection === "asc"
      ? <ChevronUp className="ml-1 h-3 w-3" />
      : <ChevronDown className="ml-1 h-3 w-3" />;
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "whitespace-nowrap px-4 py-3 text-xs font-semibold text-muted-foreground",
                    alignClass[col.align || "left"],
                  )}
                >
                  <button
                    type="button"
                    onClick={() => handleSort(col.key)}
                    className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors"
                  >
                    {col.label}
                    <SortIcon columnKey={col.key} />
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, rowIndex) => {
              const id = row[rowIdKey] ?? rowIndex;
              return (
                <tr
                  key={String(id)}
                  className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors"
                >
                  {columns.map((col) => {
                    const value = row[col.key];
                    const colorClass = getCellColor(value, col.format);
                    return (
                      <td
                        key={col.key}
                        className={cn(
                          "px-4 py-3 text-foreground",
                          alignClass[col.align || "left"],
                          col.priority !== "primary" && "whitespace-nowrap",
                          colorClass,
                        )}
                      >
                        {formatValue(value, col.format)}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {sortedRows.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-muted-foreground">
          No rows available.
        </div>
      )}
    </div>
  );
};

export default DataTable;
