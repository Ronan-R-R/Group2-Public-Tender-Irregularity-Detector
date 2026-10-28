import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetCachesForTests } from "../data/load";
import { detail, index, row } from "../test/fixtures";
import { TenderDetail } from "./TenderDetail";
import type { AwardDetail } from "../data/types";

// Turn a JavaScript value into a JSON HTTP response, like the page's fetch calls receive.
function respond(body: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

// Replace fetch with responses containing one fictional tender and its supplier match.
// Each test supplies a different match state to check the corresponding panel display.
function mockTenderPage({
  awardId,
  supplierName,
  supplierMatch,
}: {
  awardId: string;
  supplierName: string;
  supplierMatch: Exclude<AwardDetail["supplier_match"], undefined>;
}) {
  vi.stubGlobal(
    "fetch",
      vi.fn((input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const path = new URL(url, "http://localhost").pathname;

      // The page first requests the award index. Return one row for this test.
      if (path.endsWith("/data/index.json")) {
        return respond(
          index([
            row({
              id: awardId,
              title: "Fictional tender award",
              buyer: "Fictional Department of Health",
              buyer_id: "buyer-1",
              supplier: supplierName,
              supplier_id: `supplier-${awardId}`,
              shard: "ab",
            }),
          ]),
        );
      }

      // The page then requests the detail shard. Attach the requested match state.
      if (path.endsWith("/data/details/ab.json")) {
        return respond({
          [awardId]: detail({
            id: awardId,
            supplier_match: supplierMatch,
          }),
        });
      }

      // Return an empty response for any other request the page makes.
      return respond({ error: `Unmocked request: ${path}`}, 404);
    }),
  );
}

describe("TenderDetail supplier match panel", () => {
  beforeEach(() => {
    // Reset cached responses and stub scrolling before each test.
    resetCachesForTests();
    vi.stubGlobal("scrollTo", vi.fn());
  });

  afterEach(() => {
    // Remove global mocks so they do not leak into other tests.
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the not-matched message when there is no supplier match", async () => {
    // Simulate an award whose supplier has not been matched to a company.
    mockTenderPage({
      awardId: "award-null",
      supplierName: "Fictional No Match Supplier",
      supplierMatch: null,
    });

    // Render the real page with this test's award.
    render(<TenderDetail id="award-null" />);

    // Wait for the page to load and verify the message the user should see.
    expect(
      await screen.findByText(
        "Not matched to CIPC yet, so the company age, director and sector checks (R1 to R6 and R9) cannot run.",
      ),
    ).toBeTruthy();
  });

  
it("shows the exact-match message when the supplier matches exactly", async () => {
  // Simulate a supplier whose name exactly matches a registered company.
    mockTenderPage({
      awardId: "award-exact",
      supplierName: "Fictional Exact Match Services",
      supplierMatch: {
        status: "exact",
        confidence: 1,
        matched_company_name: "Fictional Exact Match Services",
        source: "sample",
      },
    });

  render(<TenderDetail id="award-exact" />);

  // Verify the explanation, suggested company, and full similarity score.
  expect(
    await screen.findByText("Exact name match after normalization."),
  ).toBeTruthy();

  expect(
    screen.getByText(
      "Suggested company: Fictional Exact Match Services",
    ),
  ).toBeTruthy();

  
  expect(
    screen.getByText(/Name-similarity score: 100\/100/i),
  ).toBeTruthy();
});


  it("shows the strong fuzzy message with the suggested company and score", async () => {
    // Simulate a likely name match that still needs a person to review it.
    mockTenderPage({
      awardId: "award-strong-fuzzy",
      supplierName: "Fictional Strong Fuzzy Supply Co",
      supplierMatch: {
        status: "strong_fuzzy",
        confidence: 0.87,
        matched_company_name: "Fictional Strong Fuzzy Supplies",
        source: "sample",
      },
    });

    render(<TenderDetail id="award-strong-fuzzy" />);

    // Verify the review warning, suggested company, and formatted score.
    expect(
      await screen.findByText(
        "Possible name match; manual review is recommended.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByText("Suggested company: Fictional Strong Fuzzy Supplies"),
    ).toBeTruthy();
    expect(screen.getByText(/Name-similarity score: 87\/100/i)).toBeTruthy();
  });

  it("shows the needs-review message with the suggested company and score", async () => {
    // Simulate a potential match that explicitly requires manual review.
    mockTenderPage({
      awardId: "award-needs-review",
      supplierName: "Fictional Needs Review Logistics",
      supplierMatch: {
        status: "needs_review",
        confidence: 0.73,
        matched_company_name: "Fictional Needs Review Logistics Group",
        source: "sample",
      },
    });

    render(<TenderDetail id="award-needs-review" />);

    // Verify the warning, suggested company, and score are all visible.
    expect(
      await screen.findByText("Potential match requires manual review."),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "Suggested company: Fictional Needs Review Logistics Group",
      ),
    ).toBeTruthy();
    expect(screen.getByText(/Name-similarity score: 73\/100/i)).toBeTruthy();
  });

  it("shows the no-match message without a score line", async () => {
    // Simulate a supplier for which no company match was found.
    mockTenderPage({
      awardId: "award-no-match",
      supplierName: "Fictional No Match Distribution",
      supplierMatch: {
        status: "no_match",
        confidence: 0.15,
        matched_company_name: null,
        source: "sample",
      },
    });

    render(<TenderDetail id="award-no-match" />);

    // Verify the no-match message is shown.
    expect(
      await screen.findByText("No company match found in the available data."),
    ).toBeTruthy();

    // A no-match result should not display a similarity score or suggestion.
    expect(screen.queryByText(/Name-similarity score:/i)).toBeNull();
    expect(screen.queryByText(/Suggested company:/i)).toBeNull();
  });
});