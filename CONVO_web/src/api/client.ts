import { env } from "@/config/env"

export class ApiClientError extends Error {
  public readonly status: number
  public readonly errors?: unknown

  constructor(
    message: string,
    status: number,
    errors?: unknown,
  ) {
    super(message)
    this.name = "ApiClientError"
    this.status = status
    this.errors = errors
  }
}

interface ApiSuccess<T> {
  success: true
  message: string
  data?: T
}

interface ApiFailure {
  success: false
  message: string
  errors?: unknown
}

type ApiResponse<T> = ApiSuccess<T> | ApiFailure

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<ApiSuccess<T>> {
  const headers = new Headers(options.headers)
  const isFormData = options.body instanceof FormData

  if (options.body && !isFormData) {
    headers.set("Content-Type", "application/json")
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`)
  }

  let response: Response

  try {
    response = await fetch(`${env.identityApiBaseUrl}${path}`, {
      ...options,
      headers,
    })
  } catch {
    throw new ApiClientError(
      "Unable to connect to the CONVO Identity service.",
      0,
    )
  }

  let payload: ApiResponse<T>

  try {
    payload = (await response.json()) as ApiResponse<T>
  } catch {
    throw new ApiClientError(
      "The server returned an invalid response.",
      response.status,
    )
  }

  if (!response.ok || !payload.success) {
    const failure = payload as ApiFailure

    throw new ApiClientError(
      failure.message || "The request failed.",
      response.status,
      failure.errors,
    )
  }

  return payload
}
