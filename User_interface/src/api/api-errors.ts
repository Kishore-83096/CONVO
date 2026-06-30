export interface ApiFieldErrors {
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;

  readonly errors?: ApiFieldErrors;

  readonly response?: unknown;

  constructor(
    message: string,
    status: number,
    errors?: ApiFieldErrors,
    response?: unknown,
  ) {
    super(message);

    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
    this.response = response;

    Object.setPrototypeOf(this, ApiError.prototype);
  }

  /**
   * Returns validation messages for a field.
   */
  getFieldError(field: string): string | undefined {
    const value = this.errors?.[field];

    if (typeof value === "string") {
      return value;
    }

    if (
      Array.isArray(value) &&
      value.length > 0 &&
      typeof value[0] === "string"
    ) {
      return value[0];
    }

    return undefined;
  }

  /**
   * True if the backend returned validation errors.
   */
  hasValidationErrors(): boolean {
    return (
      this.errors !== undefined &&
      Object.keys(this.errors).length > 0
    );
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}