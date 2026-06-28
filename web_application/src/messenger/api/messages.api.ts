import { messengerRequest } from "./messenger-client"

import type {
  SendDirectMessageRequest,
  SendDirectMessageResponse,
  SendDirectMessageResult,
} from "./messenger-api.types"

export async function sendDirectMessage(
  request: SendDirectMessageRequest,
  accessToken: string,
): Promise<SendDirectMessageResponse> {
  return messengerRequest<SendDirectMessageResult>(
    "/messages/direct/",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}
