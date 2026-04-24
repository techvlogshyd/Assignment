import { useEffect, useState } from "react";
import { fetchStats } from "../api/orders";
import type { OrderStats } from "../types";

export function useStats() {
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = () => {
      setLoading(true);
      fetchStats()
        .then(setStats)
        .catch(() => null)
        .finally(() => setLoading(false));
    };

    fetch();

    const id = setInterval(fetch, 10_000);
    // BUG F4: no return () => clearInterval(id) — interval leaks on every re-render
  }, []);

  return { stats, loading };
}
