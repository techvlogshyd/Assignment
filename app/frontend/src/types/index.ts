export type UserRole = "admin" | "editor" | "viewer";

export type OrderStatus = "pending" | "processing" | "completed" | "failed";

export interface OrderItem {
  name: string;
  price: number;
  quantity: number;
}

export interface Order {
  id: string;
  external_id: string;
  customer_name: string;
  items: OrderItem[];
  total_amount: number;
  status: OrderStatus;
  created_at: string;
  updated_at: string;
}

export interface PaginatedOrders {
  items: Order[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface OrderStats {
  total_orders: number;
  by_status: Record<OrderStatus, number>;
  total_amount: number;
}

export interface TokenPayload {
  sub: string;
  exp: number;
  role?: UserRole;
}

export interface OrderFilters {
  status?: OrderStatus | "";
  customer_name?: string;
  start_date?: string;
  end_date?: string;
}
