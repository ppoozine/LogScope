import { renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useLibraryOverviewCopilotContext } from "@/lib/copilot/hooks/use-library-overview-context";
import { useCopilotStore } from "@/lib/copilot/store";

beforeEach(() => {
  useCopilotStore.setState({
    isOpen: false,
    messages: [],
    pageContext: null,
    isStreaming: false,
    abortController: null,
    editorBridge: { setVrl: null, getVrl: () => "" },
  });
});

describe("useLibraryOverviewCopilotContext", () => {
  it("pushes overview ctx on mount and clears on unmount", () => {
    const { unmount } = renderHook(() =>
      useLibraryOverviewCopilotContext({
        filters: { status: "published", q: undefined },
        groups: [
          {
            vendor: { slug: "paloalto" },
            products: [
              {
                slug: "pan-os",
                isEmpty: false,
                logTypeCounts: { total: 2, published: 1, draft: 1 },
              },
              {
                slug: "panorama",
                isEmpty: true,
                logTypeCounts: { total: 0, published: 0, draft: 0 },
              },
            ],
          },
          {
            vendor: { slug: "cisco" },
            products: [
              {
                slug: "asa",
                isEmpty: false,
                logTypeCounts: { total: 1, published: 0, draft: 1 },
              },
            ],
          },
        ],
      }),
    );

    const ctx = useCopilotStore.getState().pageContext;
    expect(ctx).not.toBeNull();
    if (!ctx || ctx.page !== "library_overview") throw new Error("expected library_overview ctx");
    expect(ctx.vendorCount).toBe(2);
    expect(ctx.productCount).toBe(3);
    expect(ctx.productsMissingParseRule).toEqual([
      "paloalto/panorama", // is_empty
      "cisco/asa", // published === 0
    ]);
    expect(ctx.filters.status).toBe("published");

    unmount();
    expect(useCopilotStore.getState().pageContext).toBeNull();
  });

  it("survives empty groups", () => {
    renderHook(() =>
      useLibraryOverviewCopilotContext({
        filters: {},
        groups: [],
      }),
    );
    const ctx = useCopilotStore.getState().pageContext;
    if (!ctx || ctx.page !== "library_overview") throw new Error("expected library_overview ctx");
    expect(ctx.vendorCount).toBe(0);
    expect(ctx.productCount).toBe(0);
    expect(ctx.productsMissingParseRule).toEqual([]);
  });
});
