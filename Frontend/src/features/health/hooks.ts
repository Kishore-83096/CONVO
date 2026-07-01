import { useQuery } from "@tanstack/react-query";

import { getIdentityHealthAll, getMessengerHealth } from "./api";

export function useIdentityHealthAll() {
  return useQuery({
    queryKey: ["identity-health-all"],
    queryFn: getIdentityHealthAll,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}

export function useMessengerHealth() {
  return useQuery({
    queryKey: ["messenger-health"],
    queryFn: getMessengerHealth,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}