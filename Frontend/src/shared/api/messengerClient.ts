import axios, { type AxiosRequestConfig } from "axios";
import { env } from "../utils/env";
import { readAuthTokenForRequest } from "./authTokenBridge";
import { normalizeAxiosError } from "./errors";
import type { ApiResult } from "./responseEnvelope";
import { normalizeMessengerResponse } from "./responseEnvelope";

export const messengerClient = axios.create({
  baseURL: env.messengerApiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: env.apiTimeoutMs,
});

messengerClient.interceptors.request.use(async (config) => {
  const token = await readAuthTokenForRequest();

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export async function messengerRequest<T>(
  config: AxiosRequestConfig,
): Promise<ApiResult<T>> {
  try {
    const response = await messengerClient.request<unknown>(config);

    return normalizeMessengerResponse<T>(response.status, response.data);
  } catch (error) {
    return normalizeAxiosError<T>(error);
  }
}
