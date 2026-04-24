import { Link } from "react-router-dom";
import type { Order } from "../types";
import { StatusBadge } from "./StatusBadge";
import { DeleteButton } from "./DeleteButton";

interface OrderTableProps {
  orders: Order[];
  onRefresh: () => void;
}

export function OrderTable({ orders, onRefresh }: OrderTableProps) {
  if (orders.length === 0) {
    return <p className="text-gray-500 text-sm mt-4">No orders found.</p>;
  }

  return (
    <div className="overflow-x-auto mt-4">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium text-gray-700">Customer</th>
            <th className="px-4 py-2 text-left font-medium text-gray-700">External ID</th>
            <th className="px-4 py-2 text-left font-medium text-gray-700">Status</th>
            <th className="px-4 py-2 text-left font-medium text-gray-700">Amount</th>
            <th className="px-4 py-2 text-left font-medium text-gray-700">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {orders.map((order) => (
            <tr key={order.id} className="hover:bg-gray-50">
              <td className="px-4 py-2">
                <Link to={`/orders/${order.id}`} className="text-blue-600 hover:underline">
                  {order.customer_name}
                </Link>
              </td>
              <td className="px-4 py-2 font-mono text-xs text-gray-600">
                {order.external_id}
              </td>
              <td className="px-4 py-2">
                <StatusBadge status={order.status} />
              </td>
              <td className="px-4 py-2">${order.total_amount.toFixed(2)}</td>
              <td className="px-4 py-2">
                <DeleteButton orderId={order.id} onDeleted={onRefresh} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
