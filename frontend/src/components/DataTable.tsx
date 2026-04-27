import React, { useMemo, useState } from "react";
import {
  alpha,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
  useTheme,
} from "@mui/material";

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

  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }

  return String(left).localeCompare(String(right), undefined, {
    numeric: true,
    sensitivity: "base",
  });
};

const formatValue = (value: unknown, format?: DataTableColumnFormat) => {
  if (value == null || value === "") {
    return "-";
  }

  if (!format) {
    return String(value);
  }

  const numberValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numberValue)) {
    return String(value);
  }

  const decimals = format.decimals ?? 0;

  if (format.kind === "currency") {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: format.currency || "USD",
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(numberValue);
  }

  if (format.kind === "percent") {
    const percentValue = format.basis === "unit" ? numberValue : numberValue * 100;
    const prefix = format.showSign && percentValue > 0 ? "+" : "";
    return `${prefix}${percentValue.toFixed(decimals)}%`;
  }

  if (format.kind === "delta") {
    const prefix = format.showSign && numberValue > 0 ? "+" : "";
    return `${prefix}${numberValue.toFixed(decimals)}`;
  }

  return new Intl.NumberFormat("en-US", {
    notation: format.compact ? "compact" : "standard",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(numberValue);
};

const getCellColor = (value: unknown, format: DataTableColumnFormat | undefined, themeMode: "light" | "dark") => {
  if (!format || (format.kind !== "delta" && format.kind !== "percent")) {
    return undefined;
  }

  const numberValue = typeof value === "number" ? value : Number(value);
  if (Number.isNaN(numberValue) || numberValue === 0) {
    return undefined;
  }

  const positive = format.upIsPositive === false ? numberValue < 0 : numberValue > 0;
  if (positive) {
    return themeMode === "dark" ? "#6fe09b" : "#138a36";
  }

  return themeMode === "dark" ? "#ff8d8d" : "#d11f1f";
};

const DataTable: React.FC<DataTableProps> = ({ columns, data, rowIdKey }) => {
  const muiTheme = useTheme();
  const [sortKey, setSortKey] = useState<string>(columns[0]?.key || rowIdKey);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedRows = useMemo(() => {
    const nextRows = [...data];
    nextRows.sort((left, right) => {
      const result = compareValues(left[sortKey], right[sortKey]);
      return sortDirection === "asc" ? result : -result;
    });
    return nextRows;
  }, [data, sortDirection, sortKey]);

  const handleSort = (columnKey: string) => {
    if (sortKey === columnKey) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(columnKey);
    setSortDirection("asc");
  };

  return (
    <TableContainer
      sx={{
        borderRadius: 2.5,
        border: "1px solid",
        borderColor: alpha(muiTheme.palette.divider, 0.9),
        bgcolor: muiTheme.palette.background.paper,
        overflowX: "auto",
      }}
    >
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell
                key={column.key}
                align={column.align || "left"}
                sortDirection={sortKey === column.key ? sortDirection : false}
                sx={{
                  bgcolor: muiTheme.palette.background.paper,
                  borderBottomColor: alpha(muiTheme.palette.divider, 0.9),
                  whiteSpace: "nowrap",
                }}
              >
                <TableSortLabel
                  active={sortKey === column.key}
                  direction={sortKey === column.key ? sortDirection : "asc"}
                  onClick={() => handleSort(column.key)}
                >
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {column.label}
                  </Typography>
                </TableSortLabel>
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedRows.map((row, rowIndex) => {
            const fallbackId = row[rowIdKey] ?? rowIndex;
            return (
              <TableRow
                key={String(fallbackId)}
                hover
                sx={{
                  "&:last-child td": { borderBottom: 0 },
                }}
              >
                {columns.map((column) => {
                  const value = row[column.key];
                  return (
                    <TableCell
                      key={column.key}
                      align={column.align || "left"}
                      sx={{
                        borderBottomColor: alpha(muiTheme.palette.divider, 0.7),
                        color: getCellColor(value, column.format, muiTheme.palette.mode),
                        whiteSpace: column.priority === "primary" ? "normal" : "nowrap",
                      }}
                    >
                      {formatValue(value, column.format)}
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {sortedRows.length === 0 ? (
        <Box sx={{ px: 2, py: 3 }}>
          <Typography variant="body2" color="text.secondary">
            No rows available.
          </Typography>
        </Box>
      ) : null}
    </TableContainer>
  );
};

export default DataTable;