import { messengerRequest } from "./messenger-client"

import type {
  ClaimPreKeyBundlesRequest,
  ClaimPreKeyBundlesResponse,
  ClaimPreKeyBundlesResult,
} from "./messenger-api.types"

export async function claimPreKeyBundles(
  request: ClaimPreKeyBundlesRequest,
  accessToken: string,
): Promise<ClaimPreKeyBundlesResponse> {
  return messengerRequest<ClaimPreKeyBundlesResult>(
    "/e2ee/prekey-bundles/claim/",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}
