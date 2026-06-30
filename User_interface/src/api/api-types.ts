/**
 * Generic API envelope returned by most backend endpoints.
 */
export interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data?: T;
  errors?: Record<string, unknown>;
}

/**
 * Standard API error response.
 */
export interface ApiErrorResponse {
  success: false;
  message: string;
  errors?: Record<string, unknown>;
}

/**
 * Authenticated identity user.
 */
export interface IdentityUser {
  full_name: string;
  username: string;
  email: string;
  contact_number: number;
}

/**
 * Authentication response.
 */
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: IdentityUser;
}

/**
 * Generic paginated response.
 */
export interface CursorPagination<T> {
  next: string | null;
  previous: string | null;
  messages: T[];
}

/**
 * Generic API dictionary.
 */
export type JsonObject = Record<string, unknown>;