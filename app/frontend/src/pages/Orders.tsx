import { useState } from "react";
import type { OrderFilters, OrderStatus } from "../types";
import { useOrders } from "../hooks/useOrders";
import { OrderTable } from "../components/OrderTable";
import { Pagination } from "../components/Pagination";

const STATUS_OPTIONS: Array<{ label: string; value: OrderStatus | "" }> = [
  { label: "All Statuses", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
];

export function OrdersPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<OrderFilters>({});
  const { orders, total, loading } = useOrders(page, filters);

  const handleFilterChange = (patch: Partial<OrderFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch }));
    setPage(1);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Orders</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        {/* BUG F7: <select> has no associated <label> — missing htmlFor/id pairing */}
        <select
          value={filters.status ?? ""}
          onChange={(e) =>
            handleFilterChange({ status: e.target.value as OrderStatus | "" })
          }
          className="border rounded px-3 py-1.5 text-sm"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <input
          type="text"
          placeholder="Customer name…"
          value={filters.customer_name ?? ""}
          onChange={(e) => handleFilterChange({ customer_name: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm"
        />

        <input
          type="date"
          value={filters.start_date ?? ""}
          onChange={(e) => handleFilterChange({ start_date: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm"
        />
        <input
          type="date"
          value={filters.end_date ?? ""}
          onChange={(e) => handleFilterChange({ end_date: e.target.value })}
          className="border rounded px-3 py-1.5 text-sm"
        />
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : (
        <>
          <OrderTable orders={orders} onRefresh={() => setPage((p) => p)} />
          <Pagination
            page={page}
            pageSize={20}
            totalItems={total}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
