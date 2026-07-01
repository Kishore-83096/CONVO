import { messengerRequest } from "../../shared/api/messengerClient";

import type { MessengerWhoamiResponse } from "./types";

export function getMessengerWhoami() {
  return messengerRequest<MessengerWhoamiResponse>({
    method: "GET",
    url: "/auth/whoami/",
  });
}