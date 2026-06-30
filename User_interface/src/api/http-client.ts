import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
} from "axios";

import { ApiError } from "./api-errors";

let accessToken: string | null = null;

/**
 * Updates the bearer token used by all API clients.
 */
export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/**
 * Creates a configured Axios client for a backend service.
 */
export function createHttpClient(baseURL: string): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
  });

  client.interceptors.request.use(
    (config) => {
      if (accessToken) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }

      if (
        typeof FormData !== "undefined" &&
        config.data instanceof FormData
      ) {
        config.headers.delete("Content-Type");
      }

      return config;
    },
    (error) => Promise.reject(error),
  );

  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      if (!error.response) {
        throw new ApiError(
          "Unable to reach the server. Check that the backend is running and the frontend origin is allowed by CORS.",
          0,
          undefined,
          error,
        );
      }

      const status = error.response?.status ?? 500;

      const payload = error.response?.data as
        | {
            message?: string;
            errors?: Record<string, unknown>;
          }
        | undefined;

      throw new ApiError(
        payload?.message ?? "Unexpected server error.",
        status,
        payload?.errors,
        payload,
      );
    },
  );

  return client;
}

/**
 * Shared typed request helper.
 */
export async function request<T>(
  client: AxiosInstance,
  config: AxiosRequestConfig,
): Promise<T> {
  const response = await client.request<T>(config);

  return response.data;
}
