"use client";

import { useEffect, useState } from "react";

/**
 * Reactive media query hook. Returns `false` during SSR and on the server pass
 * of hydration; flips to the real value after the effect runs on the client.
 * Components that branch on the result should be tolerant of an initial
 * `false` to avoid hydration mismatches.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}
