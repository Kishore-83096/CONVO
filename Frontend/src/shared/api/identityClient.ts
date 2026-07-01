import axios, { type AxiosRequestConfig } from "axios";
import { env } from "../utils/env";
import { readAuthTokenForRequest } from "./authTokenBridge";
import { normalizeAxiosError } from "./errors";
import type { ApiResult, IdentityEnvelope } from "./responseEnvelope";
import { normalizeIdentityResponse } from "./responseEnvelope";

export const identityClient = axios.create({
  baseURL: env.identityApiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: env.apiTimeoutMs,
});

identityClient.interceptors.request.use(async (config) => {
  const token = await readAuthTokenForRequest();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export async function identityRequest<T>(
  config: AxiosRequestConfig,
): Promise<ApiResult<T>> {
  try {
    const response = await identityClient.request<IdentityEnvelope<T> | T>(
      config,
    );

    return normalizeIdentityResponse<T>(response.status, response.data);
  } catch (error) {
    return normalizeAxiosError<T>(error);
  }
}
