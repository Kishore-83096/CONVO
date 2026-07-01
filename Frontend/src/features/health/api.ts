import { identityRequest } from "../../shared/api/identityClient";
import { messengerRequest } from "../../shared/api/messengerClient";
import type { ApiResult } from "../../shared/api/responseEnvelope";
import type {
  IdentityHealthAllResponse,
  MessengerHealthResponse,
} from "./types";

export async function getIdentityHealthAll(): Promise<
  ApiResult<IdentityHealthAllResponse>
> {
  return identityRequest<IdentityHealthAllResponse>({
    method: "GET",
    url: "/health/all",
  });
}

export async function getMessengerHealth(): Promise<
  ApiResult<MessengerHealthResponse>
> {
  return messengerRequest<MessengerHealthResponse>({
    method: "GET",
    url: "/health/",
  });
}