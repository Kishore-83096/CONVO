import { messengerRequest } from "./messenger-client"

import type {
  UUID,
  UploadOneTimePreKeysRequest,
  UploadOneTimePreKeysResponse,
  UploadOneTimePreKeysResult,
} from "./messenger-api.types"

export async function uploadOneTimePreKeys(
  deviceId: UUID,
  request: UploadOneTimePreKeysRequest,
  accessToken: string,
): Promise<UploadOneTimePreKeysResponse> {
  return messengerRequest<UploadOneTimePreKeysResult>(
    `/e2ee/devices/${deviceId}/prekeys/`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}
