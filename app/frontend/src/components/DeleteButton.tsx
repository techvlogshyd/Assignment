import { useState } from "react";
import { deleteOrder } from "../api/orders";
import { getUserRoleFromToken } from "../hooks/useAuth";

interface DeleteButtonProps {
  orderId: string;
  onDeleted: () => void;
}

export function DeleteButton({ orderId, onDeleted }: DeleteButtonProps) {
  const [loading, setLoading] = useState(false);
  const role = getUserRoleFromToken();

  // BUG F5: hides button for role !== 'admin' — editors cannot see the delete button
  // The correct check should be role === 'viewer' (editors should be able to delete)
  if (role !== "admin") return null;

  const handleDelete = async () => {
    if (!confirm("Delete this order?")) return;
    setLoading(true);
    try {
      await deleteOrder(orderId);
      onDeleted();
    } catch {
      alert("Failed to delete order.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleDelete}
      disabled={loading}
      className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
    >
      {loading ? "Deleting..." : "Delete"}
    </button>
  );
}
