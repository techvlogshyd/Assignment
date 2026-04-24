interface PaginationProps {
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
}

export function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
}: PaginationProps) {
  // BUG F3: Math.floor instead of Math.ceil — last page hidden when totalItems % pageSize !== 0
  const totalPages = Math.floor(totalItems / pageSize);

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center gap-2 mt-4">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="px-3 py-1 border rounded disabled:opacity-50"
      >
        Previous
      </button>
      <span className="text-sm text-gray-600">
        Page {page} of {totalPages}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="px-3 py-1 border rounded disabled:opacity-50"
      >
        Next
      </button>
    </div>
  );
}
