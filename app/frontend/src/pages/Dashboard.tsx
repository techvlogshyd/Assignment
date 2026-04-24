import { Link } from "react-router-dom";
import { useStats } from "../hooks/useStats";
import { useOrders } from "../hooks/useOrders";
import { OrderTable } from "../components/OrderTable";
import { useState } from "react";

export function DashboardPage() {
  const { stats, loading: statsLoading } = useStats();
  const [page, setPage] = useState(1);
  // F4 leaks via useStats — setInterval without clearInterval fires on this page
  const { orders, loading: ordersLoading } = useOrders(page, {});

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Link to="/orders" className="text-blue-600 hover:underline text-sm">
          View all orders →
        </Link>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <SummaryCard
          label="Total Orders"
          value={statsLoading ? "…" : String(stats?.total_orders ?? 0)}
        />
        <SummaryCard
          label="Pending"
          value={statsLoading ? "…" : String(stats?.by_status.pending ?? 0)}
        />
        <SummaryCard
          label="Completed"
          value={statsLoading ? "…" : String(stats?.by_status.completed ?? 0)}
        />
        <SummaryCard
          label="Total Revenue"
          value={
            statsLoading
              ? "…"
              : `$${(stats?.total_amount ?? 0).toFixed(2)}`
          }
        />
      </div>

      {/* Recent orders */}
      <h2 className="text-lg font-semibold mb-2">Recent Orders</h2>
      {ordersLoading ? (
        <p className="text-gray-500 text-sm">Loading…</p>
      ) : (
        <OrderTable orders={orders.slice(0, 10)} onRefresh={() => setPage(1)} />
      )}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border rounded p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}
