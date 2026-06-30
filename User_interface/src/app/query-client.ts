import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,

      staleTime: 60 * 1000,

      gcTime: 5 * 60 * 1000,

      refetchOnWindowFocus: false,

      refetchOnReconnect: true,

      refetchOnMount: true,
    },

    mutations: {
      retry: 0,
    },
  },
});

export default queryClient;