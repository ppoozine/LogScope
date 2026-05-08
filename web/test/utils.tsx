import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, render as rtlRender } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithClient(
  ui: ReactElement,
  options?: { client?: QueryClient } & Omit<RenderOptions, "wrapper">,
) {
  const client = options?.client ?? makeQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return {
    client,
    ...rtlRender(ui, { wrapper: Wrapper, ...options }),
  };
}
