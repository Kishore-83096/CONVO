import { messengerRequest } from "./messenger-client"

import type {
  RegisterDeviceRequest,
  RegisterDeviceResponse,
  RegisterDeviceResult,
} from "./messenger-api.types"

export async function registerMessengerDevice(
  request: RegisterDeviceRequest,
  accessToken: string,
): Promise<RegisterDeviceResponse> {
  return messengerRequest<RegisterDeviceResult>(
    "/e2ee/devices/register/",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}
