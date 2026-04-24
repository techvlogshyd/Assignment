import { useEffect, useState } from "react";
import axios from "axios";
import type { Order, OrderFilters, PaginatedOrders } from "../types";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Note: using manual fetch here for fine-grained pagination control
export function useOrders(page: number, filters: OrderFilters) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const token = localStorage.getItem("token");
    const params: Record<string, string | number> = { page, page_size: 20 };
    if (filters.status) params.status = filters.status;
    if (filters.customer_name) params.customer_name = filters.customer_name;
    if (filters.start_date) params.start_date = filters.start_date;
    if (filters.end_date) params.end_date = filters.end_date;

    // BUG F2: no AbortController — rapid filter changes cause race condition
    axios
      .get<PaginatedOrders>(`${baseURL}/orders`, {
        params,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      .then((res) => {
        setOrders(res.data.items);
        setTotal(res.data.total);
      })
      .catch((err: unknown) => {
        if (err instanceof Error) setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [page]); // BUG F1: filters missing from dependency array — stale closure

  return { orders, total, loading, error };
}
