import { env } from "@/config/env"
import { clearAuthSession } from "@/app/identity/auth/auth-session"

import type {
  MessengerApiFailure,
  MessengerApiResponse,
  MessengerApiSuccess,
} from "./messenger-api.types"

export class MessengerApiError extends Error {
  public readonly status: number
  public readonly errors?: unknown

  constructor(message: string, status: number, errors?: unknown) {
    super(message)
    this.name = "MessengerApiError"
    this.status = status
    this.errors = errors
  }
}

export async function messengerRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken: string,
): Promise<MessengerApiSuccess<T>> {
  if (!env.messengerApiBaseUrl) {
    throw new MessengerApiError(
      "The Myna Messenger API URL is not configured for this deployment.",
      0,
    )
  }

  const headers = new Headers(options.headers)

  if (options.body) {
    headers.set("Content-Type", "application/json")
  }

  headers.set("Authorization", `Bearer ${accessToken}`)

  let response: Response

  try {
    response = await fetch(`${env.messengerApiBaseUrl}${path}`, {
      ...options,
      headers,
    })
  } catch {
    throw new MessengerApiError(
      "Unable to connect to the Myna Messenger service.",
      0,
    )
  }

  let payload: MessengerApiResponse<T>

  try {
    payload = (await response.clone().json()) as MessengerApiResponse<T>
  } catch {
    const text = await response.text().catch(() => "")
    const preview = text.trim().replace(/\s+/g, " ").slice(0, 120)

    throw new MessengerApiError(
      preview
        ? `The messenger service returned a non-JSON response (${response.status}): ${preview}`
        : `The messenger service returned an invalid response (${response.status}).`,
      response.status,
    )
  }

  if (response.status === 401) {
    clearAuthSession()
  }

  if (!response.ok || !payload.success) {
    const failure = payload as MessengerApiFailure

    throw new MessengerApiError(
      failure.message || "The messenger request failed.",
      response.status,
      failure.errors,
    )
  }

  return payload
}
