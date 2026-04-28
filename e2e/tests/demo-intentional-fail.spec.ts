import { test, expect } from "@playwright/test";

/**
 * Deliberately failing spec for Monday-morning triage demo (see assignment Part 2).
 * CI excludes this tag via `npm run test` (grep-invert @demo-intentional-fail).
 */
test("@demo-intentional-fail dashboard triage anchor — known red", async () => {
  expect(2 + 2).toBe(5);
});
