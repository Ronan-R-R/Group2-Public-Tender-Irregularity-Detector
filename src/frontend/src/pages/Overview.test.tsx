import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetCachesForTests } from "../data/load";
import { index, row } from "../test/fixtures";
import { Overview } from "./Overview";

function respond(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

describe("Overview", () => {
  beforeEach(() => {
    resetCachesForTests();
    window.scrollTo = vi.fn();
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders totals and the highest-scoring awards", async () => {
    const data = index([row({ id: "x", title: "Fictional bridge repair", fired: ["R10"], score: 15 }), row({ id: "y" })]);
    vi.stubGlobal("fetch", vi.fn(() => respond(data)));

    render(<Overview />);

    expect(await screen.findByText("Fictional bridge repair")).toBeTruthy();
    expect(screen.getByText("Awards with red flags")).toBeTruthy();
    expect(screen.queryByText(/corruption risk/i)).toBeNull();
  });

  it("shows an error with a working retry when the data fails to load", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(() => respond({}, 404))
      .mockImplementation(() => respond(index([row({ title: "Recovered award" })])));
    vi.stubGlobal("fetch", fetchMock);

    render(<Overview />);

    expect((await screen.findByRole("alert")).textContent).toMatch(/data file is missing/);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Recovered award")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects a file with the wrong schema", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond({ schema_version: 2, awards: [] })));

    render(<Overview />);

    expect((await screen.findByRole("alert")).textContent).toMatch(/unexpected format/);
  });
});
