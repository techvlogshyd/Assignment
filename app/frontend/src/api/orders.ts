import client from "./client";
import type {
  Order,
  OrderFilters,
  OrderStats,
  OrderStatus,
  PaginatedOrders,
} from "../types";

export async function fetchOrders(
  page: number,
  pageSize: number,
  filters: OrderFilters
): Promise<PaginatedOrders> {
  const params: Record<string, string | number> = { page, page_size: pageSize };
  if (filters.status) params.status = filters.status;
  if (filters.customer_name) params.customer_name = filters.customer_name;
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;

  const { data } = await client.get<PaginatedOrders>("/orders", { params });
  return data;
}

export async function fetchOrder(id: string): Promise<Order> {
  const { data } = await client.get<Order>(`/orders/${id}`);
  return data;
}

export async function fetchStats(): Promise<OrderStats> {
  const { data } = await client.get<OrderStats>("/orders/stats");
  return data;
}

export async function updateOrderStatus(
  id: string,
  status: OrderStatus
): Promise<Order> {
  const { data } = await client.patch<Order>(`/orders/${id}`, { status });
  return data;
}

export async function deleteOrder(id: string): Promise<void> {
  await client.delete(`/orders/${id}`);
}

export async function uploadCsv(file: File): Promise<{ created: number }> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<{ created: number }>(
    "/orders/upload-csv",
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}
