import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOrder } from "../api/orders";
import { StatusBadge } from "../components/StatusBadge";

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>();

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", id],
    queryFn: () => fetchOrder(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="p-6">Loading…</div>;
  if (isError || !order) return <div className="p-6 text-red-600">Order not found.</div>;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <Link to="/orders" className="text-blue-600 hover:underline text-sm mb-4 block">
        ← Back to orders
      </Link>

      <div className="bg-white border rounded p-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold">{order.customer_name}</h1>
          <StatusBadge status={order.status} />
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm">
          <dt className="text-gray-500">External ID</dt>
          <dd className="font-mono">{order.external_id}</dd>

          <dt className="text-gray-500">Total Amount</dt>
          <dd>${order.total_amount.toFixed(2)}</dd>

          <dt className="text-gray-500">Created</dt>
          {/* BUG F6: no timezone specified — displays UTC as local time without indication */}
          <dd>{new Date(order.created_at).toLocaleString()}</dd>

          <dt className="text-gray-500">Updated</dt>
          <dd>{new Date(order.updated_at).toLocaleString()}</dd>
        </dl>

        <div className="mt-4">
          <h2 className="font-semibold mb-2">Items</h2>
          <table className="w-full text-sm divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-1 text-left">Item</th>
                <th className="px-3 py-1 text-right">Price</th>
                <th className="px-3 py-1 text-right">Qty</th>
                <th className="px-3 py-1 text-right">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item, i) => (
                <tr key={i}>
                  <td className="px-3 py-1">{item.name}</td>
                  <td className="px-3 py-1 text-right">${item.price.toFixed(2)}</td>
                  <td className="px-3 py-1 text-right">{item.quantity}</td>
                  <td className="px-3 py-1 text-right">
                    ${(item.price * item.quantity).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
