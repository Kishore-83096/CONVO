import { messengerRequest } from "./messenger-client"

import type {
  EncryptedHistoryResponse,
  EncryptedHistoryResult,
  UUID,
} from "./messenger-api.types"

export async function getEncryptedHistory(
  roomId: UUID,
  deviceId: UUID,
  accessToken: string,
): Promise<EncryptedHistoryResponse> {
  const query = new URLSearchParams({
    device_id: deviceId,
  })

  return messengerRequest<EncryptedHistoryResult>(
    `/messages/rooms/${roomId}/history/?${query.toString()}`,
    {},
    accessToken,
  )
}
