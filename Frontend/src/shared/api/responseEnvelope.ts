export type IdentitySuccess<T> = {
  success: true;
  message?: string;
  data?: T;
};

export type IdentityError = {
  success: false;
  message: string;
  errors?: Record<string, string[] | string> | unknown;
};

export type IdentityEnvelope<T> = IdentitySuccess<T> | IdentityError;

export type ApiResult<T> =
  | {
      ok: true;
      status: number;
      data: T;
      message?: string;
    }
  | {
      ok: false;
      status: number;
      message: string;
      errors?: unknown;
    };

export function normalizeIdentityResponse<T>(
  status: number,
  body: IdentityEnvelope<T> | T,
): ApiResult<T> {
  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    body.success === true
  ) {
    return {
      ok: true,
      status,
      data: body.data as T,
      message: body.message,
    };
  }

  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    body.success === false
  ) {
    return {
      ok: false,
      status,
      message: body.message || "Request failed.",
      errors: body.errors,
    };
  }

  return {
    ok: true,
    status,
    data: body as T,
  };
}

export function normalizeMessengerResponse<T>(
  status: number,
  body: unknown,
): ApiResult<T> {
  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    body.success === true
  ) {
    const successBody = body as { data?: T; message?: string };

    return {
      ok: true,
      status,
      data: successBody.data as T,
      message: successBody.message,
    };
  }

  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    body.success === false
  ) {
    const errorBody = body as { message?: string; errors?: unknown };

    return {
      ok: false,
      status,
      message: errorBody.message || "Request failed.",
      errors: errorBody.errors,
    };
  }

  return {
    ok: true,
    status,
    data: body as T,
  };
}