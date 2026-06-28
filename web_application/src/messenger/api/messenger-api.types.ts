export type UUID = string
export type Base64String = string
export type DevicePlatform = "web" | "android" | "ios" | "desktop" | "other"

export interface MessengerApiSuccess<T> {
  success: true
  message: string
  data: T
}

export interface MessengerApiFailure {
  success: false
  message: string
  errors?: unknown
}

export type MessengerApiResponse<T> =
  | MessengerApiSuccess<T>
  | MessengerApiFailure

export interface RegisterDeviceRequest {
  device_id: UUID
  device_name: string
  platform: DevicePlatform
  registration_id: number
  identity_key_public: Base64String
  signed_prekey_id: number
  signed_prekey_public: Base64String
  signed_prekey_signature: Base64String
  key_algorithm: string
  key_bundle_version: number
}

export interface RegisterDeviceResult {
  device_id: UUID
  user_id: string
  device_created: boolean
  prekeys_created: number
  prekeys_unchanged: number
}

export type RegisterDeviceResponse =
  MessengerApiSuccess<RegisterDeviceResult>

export interface OneTimePreKeyUploadItem {
  key_id: number
  public_key: Base64String
}

export interface UploadOneTimePreKeysRequest {
  one_time_prekeys: OneTimePreKeyUploadItem[]
}

export interface UploadOneTimePreKeysResult {
  device_id: UUID
  prekeys_created: number
  prekeys_unchanged: number
}

export type UploadOneTimePreKeysResponse =
  MessengerApiSuccess<UploadOneTimePreKeysResult>

export interface ClaimPreKeyBundlesRequest {
  recipient_user_id: string
}

export interface ClaimedOneTimePreKey {
  key_id: number
  public_key: Base64String
}

export interface ClaimedSignedPreKey {
  key_id: number
  public_key: Base64String
  signature: Base64String
}

export interface ClaimedDevicePreKeyBundle {
  device_id: UUID
  registration_id: number
  identity_key_public: Base64String
  signed_prekey: ClaimedSignedPreKey
  one_time_prekey: ClaimedOneTimePreKey | null
  key_algorithm: string
  key_bundle_version: number
}

export interface ClaimPreKeyBundlesResult {
  recipient_user_id: string
  device_count: number
  devices: ClaimedDevicePreKeyBundle[]
}

export type ClaimPreKeyBundlesResponse =
  MessengerApiSuccess<ClaimPreKeyBundlesResult>

export type MessageType =
  | "text"
  | "image"
  | "video"
  | "audio"
  | "file"
  | "location"
  | "contact"
  | "system"

export type EnvelopeProtocol =
  | "double_ratchet"
  | "device_sync"
  | "group_sender_key"

export interface MessageKeyEnvelopeInput {
  recipient_device_id: UUID
  protocol: EnvelopeProtocol
  session_reference: string
  wrapped_message_key: Base64String
  key_wrap_metadata: Record<string, unknown>
  envelope_version: number
}

export interface SendDirectMessageRequest {
  recipient_user_id: string
  sender_device_id: UUID
  client_message_id: UUID
  message_type: MessageType
  encrypted_payload: Base64String
  encryption_metadata: Record<string, unknown>
  encryption_version: number
  reply_to_id?: UUID | null
  client_sent_at?: string | null
  envelopes: MessageKeyEnvelopeInput[]
}

export interface SendDirectMessageResult {
  room_id: UUID
  room_type: "direct"
  room_created: boolean
  message_id: UUID
  client_message_id: UUID
  message_created: boolean
  envelope_count: number
  created_at: string
}

export type SendDirectMessageResponse =
  MessengerApiSuccess<SendDirectMessageResult>

export interface MessageKeyEnvelopeOutput {
  recipient_user_id: string
  recipient_device_id: UUID
  protocol: EnvelopeProtocol
  session_reference: string
  wrapped_message_key: Base64String
  key_wrap_metadata: Record<string, unknown>
  envelope_version: number
}

export interface EncryptedHistoryMessage {
  id: UUID
  room_id: UUID
  sender_user_id: string
  sender_device_id: UUID
  client_message_id: UUID
  message_type: MessageType
  encrypted_payload: Base64String
  encryption_metadata: Record<string, unknown>
  encryption_version: number
  reply_to_id: UUID | null
  client_sent_at: string | null
  created_at: string
  device_envelope: MessageKeyEnvelopeOutput | null
}

export interface EncryptedHistoryResult {
  room_id: UUID
  room_type: "direct"
  device_id: UUID
  next: string | null
  previous: string | null
  messages: EncryptedHistoryMessage[]
}

export type EncryptedHistoryResponse =
  MessengerApiSuccess<EncryptedHistoryResult>

export interface RoomLastMessage {
  id: UUID
  sender_user_id: string
  message_type: MessageType
  created_at: string
}

export interface RoomListItem {
  id: UUID
  room_type: "direct" | "group"
  name: string
  member_user_ids: string[]
  other_member_user_ids: string[]
  created_at: string
  updated_at: string
  last_message: RoomLastMessage | null
}

export type RoomListResponse = MessengerApiSuccess<RoomListItem[]>
