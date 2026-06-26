Identity Service API DOCUMENTATION
=================================

This document describes every HTTP API exposed by the Identity Service service
and provides values that can be copied into Postman.


POSTMAN SETUP
-------------

Create a Postman environment with these variables:

| Variable | Example initial value | Purpose |
|---|---|---|
| `base_url` | `http://127.0.0.1:5000` | Local Identity Service service |
| `access_token` | Empty initially | Token returned by login |
| `event_id` | `1` | ID returned when an event is created |
| `contact_id` | `1` | ID returned when a contact is added |

For JSON requests, select **Body > raw > JSON** and use this header:

```text
Content-Type: application/json
```

Every authenticated request also needs:

```text
Authorization: Bearer {{access_token}}
```

Alternatively, select **Authorization > Bearer Token** in Postman and enter
`{{access_token}}`.

After a successful login, copy `data.access_token` from the response into the
`access_token` Postman environment variable.


DIRECTORY OVERVIEW
------------------

| Directory | URL prefix | Responsibility |
|---|---|---|
| `app/auth` | `/api/v1/auth` | Registration, login, password reset, logout, session revocation, and permanent account deletion |
| `app/profiles` | `/api/v1/profiles` | The logged-in user's basic profile, address, events, and Cloudinary profile picture |
| `app/contacts` | `/api/v1/contacts` | Search Myna users, save contacts, list contacts, view details, rename, and delete |
| `app/health` | `/api/v1/health` | Service, database, Cloudinary, and combined dependency health checks |
| `app/shared` | None | Shared API responses, exceptions, and error handling; it does not expose routes directly |


RESPONSE FORMAT
---------------

Successful responses use:

```json
{
  "success": true,
  "message": "Operation completed.",
  "data": {}
}
```

`data` is omitted when an operation has nothing else to return. Errors use:

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "field_name": [
      "Error description."
    ]
  }
}
```

`errors` is omitted when no field-specific information is available.

Common status codes:

| Status | Meaning |
|---:|---|
| `200` | Request succeeded |
| `201` | Resource created |
| `400` | Invalid request data or prohibited operation |
| `401` | Missing, invalid, expired, or revoked access token; or invalid login credentials |
| `404` | Requested user-owned resource or contact number was not found |
| `409` | Duplicate resource, username, or contact |
| `429` | Rate limit exceeded |
| `502` | Cloudinary operation failed |
| `503` | A service dependency is unavailable |


FRONTEND IMPLEMENTATION CONTRACT
--------------------------------

This section is normative. A frontend implementation should use these rules
instead of guessing behavior from endpoint names.

### Transport and authentication rules

| Rule | Contract |
|---|---|
| API base URL | Read from frontend configuration; use `http://127.0.0.1:5000` locally |
| API version | Every API route currently uses `/api/v1` |
| JSON requests | Send `Content-Type: application/json` and a JSON object body |
| File requests | Send `multipart/form-data` with a file field named `image`; let the browser set the boundary |
| Protected requests | Send `Authorization: Bearer <access_token>` |
| Access-token lifetime | 24 hours from login by default; use the returned `expires_at` value |
| Refresh tokens | No refresh-token endpoint currently exists |
| Missing optional resource | Individual profile endpoints return `404`; `GET /profiles/me` represents it as `null` |
| Dates | Calendar dates use `YYYY-MM-DD` |
| Timestamps | UTC ISO-8601 strings such as `2026-06-22T12:00:00+00:00` |
| Contact numbers | Exactly 10 digits; JSON number or digit string is accepted where the schema uses a contact number |
| Pagination | Contacts and events are currently returned as complete arrays; no pagination parameters exist |
| Unknown JSON fields | Do not send undocumented fields even where the backend currently ignores them |

The frontend must clear its stored access token and authenticated state after:

- Successful logout.
- Successful password reset.
- Successful account deletion.
- Any protected request returning `401` because the token is invalid, expired,
  or revoked.

Logout and password reset revoke all sessions for the user, including sessions
on other devices. There is no separate single-device logout endpoint.

### Canonical TypeScript models

These definitions match the current JSON payloads. They can be copied into a
frontend API-types module.

```ts
export interface ApiSuccess<T = never> {
  success: true;
  message: string;
  data?: T;
}

export interface ApiFailure {
  success: false;
  message: string;
  errors?: Record<string, string[]> | unknown;
}

export type ApiResponse<T = never> = ApiSuccess<T> | ApiFailure;

export interface RegisteredUser {
  full_name: string;
  username: string;
  email: string;
  contact_number: number;
}

export interface LoginUser {
  full_name: string;
  email: string;
  contact_number: number;
}

export interface LoginData {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
  user: LoginUser;
}

export interface RegisterRequest {
  full_name: string;
  username: string;
  password: string;
  confirm_password: string;
}

export interface LoginRequest {
  method: "username" | "email" | "contact_number";
  identifier: string | number;
  password: string;
}

export interface AccountCredentialsRequest {
  username: string;
  email: string;
  contact_number: string | number;
  current_password: string;
}

export interface ResetPasswordRequest extends AccountCredentialsRequest {
  new_password: string;
  confirm_new_password: string;
}

export interface Identity {
  full_name: string;
  username: string;
  email: string;
  contact_number: number;
}

export interface ProfilePicture {
  url: string;
  format: string | null;
  width: number | null;
  height: number | null;
  bytes: number | null;
  created_at: string;
  updated_at: string;
}

export interface BasicProfile {
  bio: string | null;
  date_of_birth: string | null;
  gender: string | null;
  occupation: string | null;
  website: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfileAddress {
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string | null;
  postal_code: string | null;
  country: string;
  created_at: string;
  updated_at: string;
}

export interface ProfileEvent {
  id: number;
  event_name: string;
  event_date: string;
  description: string | null;
  recurring: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompleteProfile {
  identity: Identity;
  profile_picture: ProfilePicture | null;
  basic_data: BasicProfile | null;
  address: ProfileAddress | null;
  events: ProfileEvent[];
}

export interface BasicProfileInput {
  bio?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  occupation?: string | null;
  website?: string | null;
}

export interface AddressCreateInput {
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  state?: string | null;
  postal_code?: string | null;
  country: string;
}

export type AddressUpdateInput = Partial<AddressCreateInput>;

export interface EventCreateInput {
  event_name: string;
  event_date: string;
  description?: string | null;
  recurring?: boolean;
}

export type EventUpdateInput = Partial<EventCreateInput>;

export interface ContactSearchResult {
  full_name: string;
  username: string;
  profile_picture: ProfilePicture | null;
}

export interface ContactSummary {
  id: number;
  saved_name: string;
  profile_picture: ProfilePicture | null;
}

export interface ContactDetail {
  id: number;
  saved_name: string;
  contact_number: number;
  username: string;
  full_name: string;
  profile_picture: ProfilePicture | null;
}

export interface ContactSearchRequest {
  contact_number: string | number;
}

export interface AddContactRequest extends ContactSearchRequest {
  saved_name: string;
}

export interface RenameContactRequest {
  saved_name: string;
}

export interface ComponentHealth {
  component: string;
  status: "up" | "down";
  message: string;
  latency_ms: number;
  details?: Record<string, unknown>;
}

export interface CompleteHealth {
  service: "identity-service";
  environment: string;
  status: "healthy" | "degraded";
  checks: Record<string, ComponentHealth>;
}
```

### Endpoint-to-type mapping

| Method and endpoint | Success status | `data` type |
|---|---:|---|
| `POST /api/v1/auth/register` | `201` | `RegisteredUser` |
| `POST /api/v1/auth/login` | `200` | `LoginData` |
| `POST /api/v1/auth/reset-password` | `200` | Omitted |
| `DELETE /api/v1/auth/delete-account` | `200` | Omitted |
| `POST /api/v1/auth/logout` | `200` | Omitted |
| `GET /api/v1/profiles/me` | `200` | `CompleteProfile` |
| `GET /api/v1/profiles/me/basic` | `200` | `BasicProfile` |
| `POST /api/v1/profiles/me/basic` | `201` | `BasicProfile` |
| `PATCH` or `PUT /api/v1/profiles/me/basic` | `200` | `BasicProfile` |
| `DELETE /api/v1/profiles/me/basic` | `200` | Omitted |
| `GET /api/v1/profiles/me/address` | `200` | `ProfileAddress` |
| `POST /api/v1/profiles/me/address` | `201` | `ProfileAddress` |
| `PATCH` or `PUT /api/v1/profiles/me/address` | `200` | `ProfileAddress` |
| `DELETE /api/v1/profiles/me/address` | `200` | Omitted |
| `GET /api/v1/profiles/me/events` | `200` | `ProfileEvent[]` |
| `POST /api/v1/profiles/me/events` | `201` | `ProfileEvent` |
| `GET /api/v1/profiles/me/events/:eventId` | `200` | `ProfileEvent` |
| `PATCH` or `PUT /api/v1/profiles/me/events/:eventId` | `200` | `ProfileEvent` |
| `DELETE /api/v1/profiles/me/events/:eventId` | `200` | Omitted |
| `GET /api/v1/profiles/me/picture` | `200` | `ProfilePicture` |
| `POST /api/v1/profiles/me/picture` | `201` | `ProfilePicture` |
| `PATCH` or `PUT /api/v1/profiles/me/picture` | `200` | `ProfilePicture` |
| `DELETE /api/v1/profiles/me/picture` | `200` | Omitted |
| `POST /api/v1/contacts/search` | `200` | `ContactSearchResult` |
| `POST /api/v1/contacts` | `201` | `ContactDetail` |
| `GET /api/v1/contacts` | `200` | `ContactSummary[]` |
| `GET /api/v1/contacts/:contactId` | `200` | `ContactDetail` |
| `PATCH /api/v1/contacts/:contactId` | `200` | `ContactDetail` |
| `DELETE /api/v1/contacts/:contactId` | `200` | Omitted |
| `GET /api/v1/health` | `200` | `ComponentHealth` |
| `GET /api/v1/health/database` | `200` or `503` | `ComponentHealth` |
| `GET /api/v1/health/cloudinary` | `200` or `503` | `ComponentHealth` |
| `GET /api/v1/health/all` | `200` or `503` | `CompleteHealth` |

### Recommended frontend request helper

This example treats the JSON envelope as the source of the API message and
clears authentication on any `401` response.

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly errors?: unknown,
  ) {
    super(message);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<ApiSuccess<T>> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;

  if (options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const payload = (await response.json()) as ApiResponse<T>;

  if (response.status === 401) {
    // Call the application's central clear-auth action here.
  }
  if (!response.ok || !payload.success) {
    const failure = payload as ApiFailure;
    throw new ApiClientError(
      failure.message,
      response.status,
      failure.errors,
    );
  }

  return payload;
}
```

Example JSON call:

```ts
const response = await apiRequest<ContactDetail>(
  "/api/v1/contacts",
  {
    method: "POST",
    body: JSON.stringify({
      contact_number: 9123456789,
      saved_name: "Alan",
    }),
  },
  accessToken,
);
```

Example file call:

```ts
const formData = new FormData();
formData.append("image", selectedFile);

const response = await apiRequest<ProfilePicture>(
  "/api/v1/profiles/me/picture",
  { method: "POST", body: formData },
  accessToken,
);
```

### Frontend resource-state rules

| Resource | Recommended frontend behavior |
|---|---|
| Authentication bootstrap | If a token exists, call `GET /api/v1/profiles/me`; clear auth if it returns `401` |
| Basic profile | Use `completeProfile.basic_data === null` to show create UI; otherwise show edit/delete UI |
| Address | Use `completeProfile.address === null` to choose between create and edit UI |
| Events | Use the returned event `id` for item routes and disable creation when five events exist |
| Profile picture | Use `completeProfile.profile_picture === null` to choose create versus replace UI |
| Contact search | Enable Add only when the response message is `Contact found.`; disable it for `This is your own contact.` |
| Contact list | Use `ContactSummary.id` for details, rename, and delete routes |
| Contact rename | Submit only `{ saved_name }`; all other displayed fields are read-only |
| Destructive actions | Require UI confirmation before profile deletion, contact deletion, or account deletion |

The search response currently communicates an own-contact match through the
exact message `This is your own contact.`; it does not currently include a
separate Boolean field.

### Explicit rate limits

| Endpoint | Limit |
|---|---:|
| `POST /api/v1/auth/register` | 5 requests per minute |
| `POST /api/v1/auth/login` | 10 requests per minute |
| `POST /api/v1/auth/reset-password` | 5 requests per minute |
| `DELETE /api/v1/auth/delete-account` | 3 requests per minute |
| `POST /api/v1/contacts/search` | 20 requests per minute |
| `POST /api/v1/contacts` | 20 requests per minute |

The frontend should disable repeated submit actions while requests are pending
and show the API error message if a `429` response is returned.

### Frontend error-handling matrix

| Condition | API signal | Required frontend action |
|---|---|---|
| No token supplied | `401`, `Authorization token is required.` | Redirect to login for protected screens |
| Malformed token | `401`, `Invalid authorization token.` | Clear stored auth and redirect to login |
| Expired token | `401`, `Session expired. Log in again.` | Clear stored auth and redirect to login |
| Revoked token | `401`, `Session is no longer active.` | Clear stored auth and redirect to login |
| Form validation | `400` with optional `errors` object | Display field errors where available and the top-level message |
| Missing owned resource | `404` | Show empty/not-found state; do not treat it as logout |
| Duplicate resource | `409` | Keep the form open and display the API message |
| Rate limited | `429` | Prevent immediate retry and display the API message |
| Cloudinary failure | `502` | Keep current UI data and allow a later retry |
| Dependency unavailable | `503` | Show a temporary service-unavailable state |
| Network failure/no JSON response | Fetch throws before a valid envelope is received | Show an offline/network message; do not assume the mutation completed |

The backend CORS configuration allows the single origin configured by
`FRONTEND_ORIGIN`. The deployed frontend origin must match that value exactly.


AUTH DIRECTORY
--------------

`app/auth` owns user accounts and login sessions. Registration generates the
user's Myna email and 10-digit contact number. Login creates a 24-hour access
token and an `auth_sessions` record. Password reset and logout revoke all active
sessions for the user. Account deletion permanently removes the user, their
sessions, profiles, contacts, events, address, and Cloudinary profile picture.

### Auth endpoint table

| Operation | Method | Postman URL | Authentication | Body |
|---|---|---|---|---|
| Register | `POST` | `{{base_url}}/api/v1/auth/register` | No | JSON: `full_name`, `username`, `password`, `confirm_password` |
| Login | `POST` | `{{base_url}}/api/v1/auth/login` | No | JSON: `method`, `identifier`, `password` |
| Reset password | `POST` | `{{base_url}}/api/v1/auth/reset-password` | Bearer token | JSON account credentials plus new password fields |
| Delete account | `DELETE` | `{{base_url}}/api/v1/auth/delete-account` | Bearer token | JSON: `username`, `email`, `contact_number`, `current_password` |
| Logout all sessions | `POST` | `{{base_url}}/api/v1/auth/logout` | Bearer token | No body |

### Register account

Postman body:

```json
{
  "full_name": "Ada Lovelace",
  "username": "ada_lovelace",
  "password": "correct-password",
  "confirm_password": "correct-password"
}
```

Username rules:

- 3 to 30 characters.
- Lowercase letters, numbers, and underscores only.
- A leading `@` is accepted and removed.
- The password must contain 8 to 128 characters.

Example response:

```json
{
  "success": true,
  "message": "Account created.",
  "data": {
    "full_name": "Ada Lovelace",
    "email": "ada_lovelace@Myna.com",
    "contact_number": 9876543210,
    "username": "ada_lovelace"
  }
}
```

The contact number in this document is an example. Use the number returned by
your own registration response in later requests.

### Login

Postman body using a username:

```json
{
  "method": "username",
  "identifier": "ada_lovelace",
  "password": "correct-password"
}
```

The supported identifier combinations are:

| `method` | Example `identifier` |
|---|---|
| `username` | `ada_lovelace` or `@ada_lovelace` |
| `email` | `ada_lovelace@Myna.com` |
| `contact_number` | `9876543210` |

Example response:

```json
{
  "success": true,
  "message": "User logged in.",
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_at": "2026-06-23T12:00:00+00:00",
    "user": {
      "full_name": "Ada Lovelace",
      "email": "ada_lovelace@Myna.com",
      "contact_number": 9876543210
    }
  }
}
```

### Reset password

Add the Bearer token and use this Postman body:

```json
{
  "username": "ada_lovelace",
  "email": "ada_lovelace@Myna.com",
  "contact_number": 9876543210,
  "current_password": "correct-password",
  "new_password": "new-secure-password",
  "confirm_new_password": "new-secure-password"
}
```

All identity fields and the current password must belong to the authenticated
user. The new passwords must match. A successful reset changes the password and
revokes every active session, so the user must log in again.

Example response:

```json
{
  "success": true,
  "message": "Password has been changed successfully. Log in again."
}
```

### Delete account

This operation is permanent. Add the Bearer token and use:

```json
{
  "username": "ada_lovelace",
  "email": "ada_lovelace@Myna.com",
  "contact_number": 9876543210,
  "current_password": "new-secure-password"
}
```

Example response:

```json
{
  "success": true,
  "message": "Account and all associated data deleted permanently."
}
```

If the user has a profile picture and Cloudinary deletion fails, the database
account remains unchanged and the API returns an error.

### Logout all sessions

Set the method to `POST`, add the Bearer token, and do not send a body:

```text
{{base_url}}/api/v1/auth/logout
```

Example response:

```json
{
  "success": true,
  "message": "User logged out."
}
```

This deletes all of the user's `auth_sessions` records. Every existing access
token for that user becomes invalid.


PROFILES DIRECTORY
------------------

`app/profiles` manages only the authenticated user's profile. The user's full
name, username, email, and contact number are read-only identity fields. Basic
data, address, events, and profile picture are separate resources.

Every profile endpoint requires the Bearer token.

### Profile endpoint table

| Operation | Method | Postman URL | Request body |
|---|---|---|---|
| Complete profile | `GET` | `{{base_url}}/api/v1/profiles/me` | None |
| Get basic data | `GET` | `{{base_url}}/api/v1/profiles/me/basic` | None |
| Create basic data | `POST` | `{{base_url}}/api/v1/profiles/me/basic` | Raw JSON basic fields |
| Patch basic data | `PATCH` | `{{base_url}}/api/v1/profiles/me/basic` | Raw JSON with at least one basic field |
| Put basic data | `PUT` | `{{base_url}}/api/v1/profiles/me/basic` | Raw JSON with at least one basic field |
| Delete basic data | `DELETE` | `{{base_url}}/api/v1/profiles/me/basic` | None |
| Get address | `GET` | `{{base_url}}/api/v1/profiles/me/address` | None |
| Create address | `POST` | `{{base_url}}/api/v1/profiles/me/address` | Raw JSON address fields |
| Patch address | `PATCH` | `{{base_url}}/api/v1/profiles/me/address` | Raw JSON with at least one address field |
| Put address | `PUT` | `{{base_url}}/api/v1/profiles/me/address` | Raw JSON with at least one address field |
| Delete address | `DELETE` | `{{base_url}}/api/v1/profiles/me/address` | None |
| List events | `GET` | `{{base_url}}/api/v1/profiles/me/events` | None |
| Create event | `POST` | `{{base_url}}/api/v1/profiles/me/events` | Raw JSON event fields |
| Get event | `GET` | `{{base_url}}/api/v1/profiles/me/events/{{event_id}}` | None |
| Patch event | `PATCH` | `{{base_url}}/api/v1/profiles/me/events/{{event_id}}` | Raw JSON with at least one event field |
| Put event | `PUT` | `{{base_url}}/api/v1/profiles/me/events/{{event_id}}` | Raw JSON with at least one event field |
| Delete event | `DELETE` | `{{base_url}}/api/v1/profiles/me/events/{{event_id}}` | None |
| Get profile picture | `GET` | `{{base_url}}/api/v1/profiles/me/picture` | None |
| Create profile picture | `POST` | `{{base_url}}/api/v1/profiles/me/picture` | `form-data`: `image` file |
| Patch profile picture | `PATCH` | `{{base_url}}/api/v1/profiles/me/picture` | `form-data`: `image` file |
| Put profile picture | `PUT` | `{{base_url}}/api/v1/profiles/me/picture` | `form-data`: `image` file |
| Delete profile picture | `DELETE` | `{{base_url}}/api/v1/profiles/me/picture` | None |

For every `GET` or `DELETE` operation above, choose the method and URL shown in
the table, add the Bearer token, and leave the Postman body empty.

### Complete profile example

Postman request:

```text
GET {{base_url}}/api/v1/profiles/me
Authorization: Bearer {{access_token}}
```

The response combines immutable identity data with the picture, basic data,
address, and events. Resources not created yet are returned as `null` or an
empty list.

```json
{
  "success": true,
  "message": "Profile retrieved.",
  "data": {
    "identity": {
      "full_name": "Ada Lovelace",
      "username": "ada_lovelace",
      "email": "ada_lovelace@Myna.com",
      "contact_number": 9876543210
    },
    "profile_picture": null,
    "basic_data": null,
    "address": null,
    "events": []
  }
}
```

### Basic data Postman bodies

Use this example for `POST`:

```json
{
  "bio": "Mathematician and writer.",
  "date_of_birth": "1815-12-10",
  "gender": "female",
  "occupation": "mathematician",
  "website": "https://example.com/ada"
}
```

Use a partial body for `PATCH` or `PUT`:

```json
{
  "bio": "Updated biography.",
  "occupation": "computer science pioneer"
}
```

| Field | Rules |
|---|---|
| `bio` | Optional; string up to 500 characters or `null` |
| `date_of_birth` | Optional; `YYYY-MM-DD` or `null` |
| `gender` | Optional; string up to 50 characters or `null` |
| `occupation` | Optional; string up to 100 characters or `null` |
| `website` | Optional; valid URL or `null` |

Create returns `201`. Get, patch, and put return `200`. Delete removes only the
basic profile record.

### Address Postman bodies

Use this example for `POST`:

```json
{
  "address_line_1": "12 Computing Lane",
  "address_line_2": "Apartment 4",
  "city": "London",
  "state": "England",
  "postal_code": "SW1A 1AA",
  "country": "United Kingdom"
}
```

`address_line_1`, `city`, and `country` are required when creating an address.
Use a partial body for `PATCH` or `PUT`:

```json
{
  "city": "Manchester",
  "postal_code": "M1 1AE"
}
```

Create returns `201`. Get, patch, and put return `200`. Delete removes only the
address record.

### Event Postman bodies

Use this example for `POST`:

```json
{
  "event_name": "Birthday",
  "event_date": "1815-12-10",
  "description": "Annual birthday reminder",
  "recurring": true
}
```

The create response contains an event `id`. Store that value as the Postman
`event_id` environment variable. A user can store a maximum of five events.

Use a partial body for `PATCH` or `PUT`:

```json
{
  "description": "Updated reminder",
  "recurring": false
}
```

| Field | Rules |
|---|---|
| `event_name` | Required on create; 1 to 80 characters |
| `event_date` | Required on create; `YYYY-MM-DD` |
| `description` | Optional; up to 300 characters or `null` |
| `recurring` | Optional Boolean; defaults to `true` on create |

### Profile picture Postman example

For `POST`, `PATCH`, or `PUT`:

1. Add the Bearer token.
2. Select **Body > form-data**.
3. Add a key named `image`.
4. Change the key type from **Text** to **File**.
5. Select a JPEG or PNG file.
6. Do not manually set `Content-Type`; Postman creates the multipart boundary.

The default maximum profile-picture size is 5 MB. `POST` creates the picture;
`PATCH` and `PUT` replace it in Cloudinary. A picture response has this shape:

```json
{
  "success": true,
  "message": "Profile picture created.",
  "data": {
    "url": "https://res.cloudinary.com/example/image/upload/v1/Mynav2/local/profiles/ada_lovelace.png",
    "format": "png",
    "width": 512,
    "height": 512,
    "bytes": 84521,
    "created_at": "2026-06-22T12:00:00+00:00",
    "updated_at": "2026-06-22T12:00:00+00:00"
  }
}
```


CONTACTS DIRECTORY
------------------

`app/contacts` stores a private contact list for each authenticated user. A
contact must reference another active Myna user. Searching by the logged-in
user's own contact number is allowed and is identified in the response, but a
user cannot add themselves to their contact list. Duplicate contacts are also
rejected.

Every contacts endpoint requires the Bearer token.

### Contacts endpoint table

| Operation | Method | Postman URL | Request body |
|---|---|---|---|
| Search contact | `POST` | `{{base_url}}/api/v1/contacts/search` | JSON: `contact_number` |
| Add contact | `POST` | `{{base_url}}/api/v1/contacts` | JSON: `contact_number`, `saved_name` |
| List my contacts | `GET` | `{{base_url}}/api/v1/contacts` | None |
| Get contact details | `GET` | `{{base_url}}/api/v1/contacts/{{contact_id}}` | None |
| Rename contact | `PATCH` | `{{base_url}}/api/v1/contacts/{{contact_id}}` | JSON: `saved_name` only |
| Delete contact | `DELETE` | `{{base_url}}/api/v1/contacts/{{contact_id}}` | None |

### Search contact

Postman body:

```json
{
  "contact_number": 9123456789
}
```

Example response for another user:

```json
{
  "success": true,
  "message": "Contact found.",
  "data": {
    "full_name": "Alan Turing",
    "username": "alan_turing",
    "profile_picture": {
      "url": "https://res.cloudinary.com/example/image/upload/v1/Mynav2/local/profiles/alan_turing.png",
      "format": "png",
      "width": 512,
      "height": 512,
      "bytes": 84521,
      "created_at": "2026-06-22T12:00:00+00:00",
      "updated_at": "2026-06-22T12:00:00+00:00"
    }
  }
}
```

If the number belongs to the logged-in user, the same limited details are
returned with the message `This is your own contact.`. A user without a profile
picture has `"profile_picture": null`.

### Add contact

Postman body:

```json
{
  "contact_number": 9123456789,
  "saved_name": "Alan"
}
```

The user can choose any non-empty saved name up to 100 characters. Example
response:

```json
{
  "success": true,
  "message": "Contact added.",
  "data": {
    "id": 1,
    "saved_name": "Alan",
    "contact_number": 9123456789,
    "username": "alan_turing",
    "full_name": "Alan Turing",
    "profile_picture": null
  }
}
```

Store the returned `id` as the Postman `contact_id` environment variable.

Trying to add the logged-in user's own number returns:

```json
{
  "success": false,
  "message": "You cannot add your own contact."
}
```

### List my contacts

Postman request:

```text
GET {{base_url}}/api/v1/contacts
Authorization: Bearer {{access_token}}
```

The list deliberately contains only the ID needed for later requests, the
user-chosen saved name, and profile picture:

```json
{
  "success": true,
  "message": "Contact list retrieved.",
  "data": [
    {
      "id": 1,
      "saved_name": "Alan",
      "profile_picture": null
    }
  ]
}
```

Contacts are ordered case-insensitively by saved name.

### Get one contact

Postman request:

```text
GET {{base_url}}/api/v1/contacts/{{contact_id}}
Authorization: Bearer {{access_token}}
```

Example response:

```json
{
  "success": true,
  "message": "Contact retrieved.",
  "data": {
    "id": 1,
    "saved_name": "Alan",
    "contact_number": 9123456789,
    "username": "alan_turing",
    "full_name": "Alan Turing",
    "profile_picture": null
  }
}
```

Only the contact-list owner can retrieve this record.

### Rename contact

Postman body:

```json
{
  "saved_name": "Professor Turing"
}
```

Only `saved_name` can be changed. The contact user's number, username, full
name, and picture always come from that user's current account and profile.

Example response message:

```json
{
  "success": true,
  "message": "Contact name updated.",
  "data": {
    "id": 1,
    "saved_name": "Professor Turing",
    "contact_number": 9123456789,
    "username": "alan_turing",
    "full_name": "Alan Turing",
    "profile_picture": null
  }
}
```

### Delete contact

Set the method to `DELETE`, add the Bearer token, and leave the body empty:

```text
{{base_url}}/api/v1/contacts/{{contact_id}}
```

Example response:

```json
{
  "success": true,
  "message": "Contact deleted."
}
```

Deleting a contact removes only the saved contact-list record. It does not
delete the other user's account.


HEALTH DIRECTORY
----------------

`app/health` exposes unauthenticated operational checks. Dependency checks
return `200` when available and `503` when unavailable.

### Health endpoint table

| Operation | Method | Postman URL | Authentication | Body |
|---|---|---|---|---|
| Service process | `GET` | `{{base_url}}/api/v1/health` | No | None |
| Database | `GET` | `{{base_url}}/api/v1/health/database` | No | None |
| Cloudinary | `GET` | `{{base_url}}/api/v1/health/cloudinary` | No | None |
| All dependencies | `GET` | `{{base_url}}/api/v1/health/all` | No | None |
| Root redirect | `GET` | `{{base_url}}/` | No | None; redirects to `/api/v1/health/all` |

For all health checks, select `GET` in Postman and leave Authorization and Body
empty.

Example service response:

```json
{
  "success": true,
  "message": "Identity Service service is running.",
  "data": {
    "component": "service",
    "status": "up",
    "message": "Identity Service service is running.",
    "latency_ms": 0.01
  }
}
```

Example combined response:

```json
{
  "success": true,
  "message": "All service dependencies are available.",
  "data": {
    "service": "identity-service",
    "environment": "local",
    "status": "healthy",
    "checks": {
      "service": {
        "component": "service",
        "status": "up",
        "message": "Identity Service service is running.",
        "latency_ms": 0.01
      },
      "database": {
        "component": "database",
        "status": "up",
        "message": "Database connection is available.",
        "latency_ms": 1.25,
        "details": {
          "database_engine": "postgresql"
        }
      },
      "cloudinary": {
        "component": "cloudinary",
        "status": "up",
        "message": "Cloudinary API is reachable.",
        "latency_ms": 120.5
      }
    }
  }
}
```


POSTMAN WORKFLOW
----------------

For a complete manual test, run requests in this order:

1. Register at least two users and keep both generated contact numbers.
2. Log in as the first user and save the access token.
3. Create or update profile resources.
4. Search for the second user's contact number.
5. Add the second user with a custom saved name.
6. Copy the returned contact ID into `contact_id`.
7. Test list, details, rename, and delete contact operations.
8. Test password reset, then log in again with the new password.
9. Test logout and confirm that every previous token is rejected.
10. Use permanent account deletion only with disposable test accounts.
