import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  type ProductDetailStateForCopilot,
  useProductDetailCopilotContext,
} from "@/lib/copilot/hooks/use-product-detail-context";
import { useCopilotStore } from "@/lib/copilot/store";

const baseInput: ProductDetailStateForCopilot = {
  vendorSlug: "paloalto",
  productSlug: "pan-os",
  productStatus: "active",
  activeLogType: {
    name: "traffic",
    fields: [{ name: "src_ip", type: "string", required: true }],
    samplesCount: 5,
    parseRuleHead: ". = parse_syslog!(.message)",
  },
  subTab: "overview",
  openDiff: null,
};

describe("useProductDetailCopilotContext", () => {
  it("pushes library_product ctx on overview/stats sub-tabs", () => {
    const { rerender } = renderHook(
      ({ subTab }: { subTab: ProductDetailStateForCopilot["subTab"] }) =>
        useProductDetailCopilotContext({ ...baseInput, subTab }),
      { initialProps: { subTab: "overview" } },
    );
    let ctx = useCopilotStore.getState().pageContext;
    expect(ctx?.page).toBe("library_product");

    rerender({ subTab: "stats" });
    ctx = useCopilotStore.getState().pageContext;
    expect(ctx?.page).toBe("library_product");
  });

  it("pushes library_versions ctx on versions sub-tab", () => {
    renderHook(() => useProductDetailCopilotContext({ ...baseInput, subTab: "versions" }));
    const ctx = useCopilotStore.getState().pageContext;
    expect(ctx?.page).toBe("library_versions");
    if (!ctx || ctx.page !== "library_versions") throw new Error();
    expect(ctx.logTypeName).toBe("traffic");
    expect(ctx.diff).toBeNull();
  });

  it("includes diff when openDiff provided on versions sub-tab", () => {
    renderHook(() =>
      useProductDetailCopilotContext({
        ...baseInput,
        subTab: "versions",
        openDiff: {
          baseVersion: "v3",
          headVersion: "v4",
          baseVrl: "old",
          headVrl: "new",
        },
      }),
    );
    const ctx = useCopilotStore.getState().pageContext;
    if (!ctx || ctx.page !== "library_versions") throw new Error();
    expect(ctx.diff?.headVersion).toBe("v4");
    expect(ctx.diff?.baseVrl).toBe("old");
  });

  it("ignores openDiff when not on versions sub-tab", () => {
    renderHook(() =>
      useProductDetailCopilotContext({
        ...baseInput,
        subTab: "overview",
        openDiff: {
          baseVersion: "v3",
          headVersion: "v4",
          baseVrl: "old",
          headVrl: "new",
        },
      }),
    );
    const ctx = useCopilotStore.getState().pageContext;
    expect(ctx?.page).toBe("library_product");
  });

  it("clears pageContext on unmount", () => {
    const { unmount } = renderHook(() => useProductDetailCopilotContext({ ...baseInput }));
    expect(useCopilotStore.getState().pageContext?.page).toBe("library_product");
    unmount();
    expect(useCopilotStore.getState().pageContext).toBeNull();
  });

  it("renders library_product ctx with null active log type (e.g., new product)", () => {
    renderHook(() =>
      useProductDetailCopilotContext({
        ...baseInput,
        activeLogType: null,
      }),
    );
    const ctx = useCopilotStore.getState().pageContext;
    if (!ctx || ctx.page !== "library_product") throw new Error();
    expect(ctx.activeLogType).toBeNull();
  });
});
