'use client';
import { useMemo, useState, type ReactNode } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowDownUp, ChevronLeft, ChevronRight, Search } from 'lucide-react';
import { text, type RecordData } from '@/lib/format';
import { Empty } from './ui';
export type TableColumn = {
  key: string;
  label: string;
  render?: (value: unknown, row: RecordData) => ReactNode;
};
export function DataTable({
  rows,
  columns,
  label = 'Research records',
  onSelect,
  pageSize = 10,
  filterable = true,
}: {
  rows: RecordData[];
  columns: TableColumn[];
  label?: string;
  onSelect?: (row: RecordData) => void;
  pageSize?: number;
  filterable?: boolean;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filter, setFilter] = useState('');
  const defs = useMemo<ColumnDef<RecordData>[]>(
    () =>
      columns.map((c) => ({
        id: c.key,
        accessorFn: (r) => r[c.key],
        header: c.label,
        cell: (ctx) =>
          c.render
            ? c.render(ctx.getValue(), ctx.row.original)
            : text(ctx.getValue(), ctx.getValue() == null ? 'Unavailable' : String(ctx.getValue())),
      })),
    [columns],
  );
  const table = useReactTable({
    data: rows,
    columns: defs,
    state: { sorting, globalFilter: filter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    initialState: { pagination: { pageSize } },
  });
  if (!rows.length) return <Empty title="No records in this selection" />;
  return (
    <div className="data-table">
      {filterable && (
        <div className="table-toolbar">
          <span>{rows.length.toLocaleString()} records</span>
          <label className="table-search">
            <Search size={14} />
            <input
              aria-label={`Filter ${label}`}
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                table.setPageIndex(0);
              }}
              placeholder="Filter records…"
            />
          </label>
        </div>
      )}
      <div className="table-scroll">
        <table aria-label={label}>
          <thead>
            {table.getHeaderGroups().map((g) => (
              <tr key={g.id}>
                {g.headers.map((h) => (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={
                      h.column.getIsSorted() === 'asc'
                        ? 'ascending'
                        : h.column.getIsSorted() === 'desc'
                          ? 'descending'
                          : 'none'
                    }
                  >
                    <button onClick={h.column.getToggleSortingHandler()}>
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      <ArrowDownUp size={11} />
                    </button>
                  </th>
                ))}
                {onSelect && <th scope="col">Inspect</th>}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id}>
                {r.getVisibleCells().map((c) => (
                  <td key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                ))}
                {onSelect && (
                  <td>
                    <button
                      className="text-button"
                      aria-label={`Inspect record ${r.index + 1}`}
                      onClick={() => onSelect(r.original)}
                    >
                      Details ↗
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <span>
          Page {table.getState().pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
        </span>
        <div>
          <button
            aria-label="Previous table page"
            disabled={!table.getCanPreviousPage()}
            onClick={() => table.previousPage()}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            aria-label="Next table page"
            disabled={!table.getCanNextPage()}
            onClick={() => table.nextPage()}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
