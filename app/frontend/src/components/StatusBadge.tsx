import type { OrderStatus } from "../types";

interface StatusBadgeProps {
  status: OrderStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  // BUG F7: pending/processing badges use #FFD700 on white — contrast ratio ~1.07:1
  // WCAG AA requires 4.5:1 for normal text
  const badgeStyle: Record<OrderStatus, React.CSSProperties> = {
    pending: { color: "#FFD700", backgroundColor: "#FFFFFF", border: "1px solid #ccc" },
    processing: { color: "#FFD700", backgroundColor: "#FFFFFF", border: "1px solid #ccc" },
    completed: { color: "#166534", backgroundColor: "#dcfce7", border: "none" },
    failed: { color: "#991b1b", backgroundColor: "#fee2e2", border: "none" },
  };

  return (
    <span
      style={badgeStyle[status]}
      className="px-2 py-0.5 rounded-full text-xs font-medium capitalize"
    >
      {status}
    </span>
  );
}
