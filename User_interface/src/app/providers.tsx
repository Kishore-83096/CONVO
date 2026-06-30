import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import ErrorBoundary from "./ErrorBoundary";
import { queryClient } from "./query-client";

interface AppProvidersProps {
  children: ReactNode;
}

export default function AppProviders({
  children,
}: AppProvidersProps) {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </ErrorBoundary>
  );
}