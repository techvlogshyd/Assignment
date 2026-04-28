import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it.fails(
    "F3: total page count uses ceiling so partial last page is reachable (currently Math.floor)",
    () => {
      render(
        <Pagination
          page={1}
          pageSize={20}
          totalItems={45}
          onPageChange={() => {}}
        />
      );
      expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument();
    }
  );
});
