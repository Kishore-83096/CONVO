import { useMutation } from "@tanstack/react-query";

import { getMessengerWhoami } from "./api";

export function useMessengerWhoami() {
  return useMutation({
    mutationFn: () => getMessengerWhoami(),
  });
}