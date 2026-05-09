"use client";

import { useEffect, useRef } from "react";

import { useCopilotStore } from "@/lib/copilot/store";

export type ProductDetailStateForCopilot = {
  vendorSlug: string;
  productSlug: string;
  productStatus: string;
  activeLogType: {
    name: string;
    fields: { name: string; type: string; required: boolean }[];
    samplesCount: number;
    parseRuleHead: string | null;
  } | null;
  subTab: "overview" | "stats" | "versions";
  openDiff: {
    baseVersion: string;
    headVersion: string;
    baseVrl: string | null;
    headVrl: string | null;
  } | null;
};

/**
 * Push the current /library/<vendor>/<product> view state into the Copilot
 * store as either `library_product` or `library_versions` depending on the
 * active sub-tab. Single-hook design avoids two hooks fighting over
 * setPageContext when the user toggles the Versions sub-tab.
 *
 * Cleanup clears pageContext to null so navigating away doesn't leak ctx.
 */
export function useProductDetailCopilotContext(state: ProductDetailStateForCopilot): void {
  const setPageContext = useCopilotStore((s) => s.setPageContext);

  const latestRef = useRef(state);
  latestRef.current = state;

  // JSON.stringify keys keep dep array stable while still re-firing on
  // structural change (matches the use-analyzer-context pattern).
  const altKey = JSON.stringify(state.activeLogType);
  const diffKey = JSON.stringify(state.openDiff);

  // biome-ignore lint/correctness/useExhaustiveDependencies: latestRef pattern + JSON.stringify dep keys intentionally bypass static exhaustive-deps; structural changes captured via altKey/diffKey
  useEffect(() => {
    const s = latestRef.current;
    if (s.subTab === "versions") {
      setPageContext({
        page: "library_versions",
        vendorSlug: s.vendorSlug,
        productSlug: s.productSlug,
        logTypeName: s.activeLogType?.name ?? "",
        diff: s.openDiff,
      });
    } else {
      setPageContext({
        page: "library_product",
        vendorSlug: s.vendorSlug,
        productSlug: s.productSlug,
        productStatus: s.productStatus,
        activeLogType: s.activeLogType,
      });
    }
    return () => setPageContext(null);
  }, [
    setPageContext,
    state.vendorSlug,
    state.productSlug,
    state.productStatus,
    state.subTab,
    altKey,
    diffKey,
  ]);
}
