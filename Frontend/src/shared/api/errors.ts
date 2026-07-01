import axios from "axios";

import type { ApiResult } from "./responseEnvelope";

type ErrorBody = {
  message?: string;
  detail?: string;
  errors?: unknown;
};

function getErrorMessage(status: number, body: ErrorBody | undefined): string {
  if (body?.message) {
    return body.message;
  }

  if (body?.detail) {
    return body.detail;
  }

  if (status === 400) {
    return "Validation failed. Please check the form values.";
  }

  if (status === 401) {
    return "Your session expired. Please log in again.";
  }

  if (status === 403) {
    return "You are not allowed to perform this action.";
  }

  if (status === 404) {
    return "The requested resource was not found.";
  }

  if (status === 409) {
    return "This request conflicts with existing data.";
  }

  if (status === 429) {
    return "Too many requests. Please wait and try again.";
  }

  if (status >= 500) {
    return "Server error. Please try again later.";
  }

  return "Network request failed.";
}

function isErrorBody(value: unknown): value is ErrorBody {
  return typeof value === "object" && value !== null;
}

export function normalizeAxiosError<T = never>(error: unknown): ApiResult<T> {
  if (!axios.isAxiosError(error)) {
    return {
      ok: false,
      status: 0,
      message: "Unexpected application error.",
      errors: error,
    };
  }

  const status = error.response?.status ?? 0;
  const responseBody = error.response?.data;
  const body = isErrorBody(responseBody) ? responseBody : undefined;

  return {
    ok: false,
    status,
    message: getErrorMessage(status, body),
    errors: body?.errors ?? responseBody,
  };
}