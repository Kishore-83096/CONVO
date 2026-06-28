import type {
  ClaimPreKeyBundlesResult,
  MessageKeyEnvelopeInput,
  RegisterDeviceRequest,
  SendDirectMessageRequest,
  UploadOneTimePreKeysRequest,
} from "@/messenger/api/messenger-api.types"
import {
  addStoredOneTimePreKeys,
  deleteStoredLocalDeviceState,
  getStoredLocalDeviceState,
  saveStoredLocalDeviceState,
} from "@/messenger/e2ee/device-store"
import {
  encryptMessageContent,
  messageAssociatedData,
} from "@/messenger/e2ee/message-encryption"

const publicRegistrationStorageKey = "myna.messenger.publicDeviceRegistration.v1"
const preKeyInventoryStoragePrefix = "myna.messenger.publicPreKeyInventory.v1"
const keyAlgorithm = "webcrypto-p256-dev-v1"

function bytesToBase64(bytes: ArrayBuffer) {
  const values = new Uint8Array(bytes)
  let binary = ""

  for (const value of values) {
    binary += String.fromCharCode(value)
  }

  return btoa(binary)
}

function randomRegistrationId() {
  const bytes = new Uint32Array(1)
  crypto.getRandomValues(bytes)

  return (bytes[0] % 2_147_483_646) + 1
}

function randomSignedPreKeyId() {
  const bytes = new Uint32Array(1)
  crypto.getRandomValues(bytes)

  return (bytes[0] % 2_147_483_646) + 1
}

function preKeyInventoryStorageKey(deviceId: string) {
  return `${preKeyInventoryStoragePrefix}.${deviceId}`
}

function randomPreKeyStartId() {
  const bytes = new Uint32Array(1)
  crypto.getRandomValues(bytes)

  return (bytes[0] % 1_000_000_000) + 1_000
}

function browserDeviceName() {
  const userAgentData = navigator as Navigator & {
    userAgentData?: {
      brands?: Array<{ brand: string }>
      platform?: string
    }
  }
  const browser = userAgentData.userAgentData?.brands?.[0]?.brand ?? "Browser"
  const platform = userAgentData.userAgentData?.platform ?? navigator.platform ?? "Web"

  return `${browser} on ${platform}`.slice(0, 100)
}

export function getStoredPublicDeviceRegistration() {
  const stored = localStorage.getItem(publicRegistrationStorageKey)

  if (!stored) {
    return null
  }

  try {
    return JSON.parse(stored) as RegisterDeviceRequest
  } catch {
    localStorage.removeItem(publicRegistrationStorageKey)
    return null
  }
}

export function savePublicDeviceRegistration(request: RegisterDeviceRequest) {
  localStorage.setItem(publicRegistrationStorageKey, JSON.stringify(request))
}

export function forgetPublicDeviceRegistration() {
  localStorage.removeItem(publicRegistrationStorageKey)
}

export async function forgetLocalDeviceIdentity() {
  forgetPublicDeviceRegistration()
  await deleteStoredLocalDeviceState()
}

interface PublicPreKeyInventory {
  nextKeyId: number
  uploadedBatches: number
}

export function getPublicPreKeyInventory(deviceId: string) {
  const stored = localStorage.getItem(preKeyInventoryStorageKey(deviceId))

  if (!stored) {
    return {
      nextKeyId: randomPreKeyStartId(),
      uploadedBatches: 0,
    } satisfies PublicPreKeyInventory
  }

  try {
    const inventory = JSON.parse(stored) as PublicPreKeyInventory

    if (
      Number.isInteger(inventory.nextKeyId)
      && inventory.nextKeyId > 0
      && Number.isInteger(inventory.uploadedBatches)
      && inventory.uploadedBatches >= 0
    ) {
      return inventory
    }
  } catch {
    localStorage.removeItem(preKeyInventoryStorageKey(deviceId))
  }

  return {
    nextKeyId: randomPreKeyStartId(),
    uploadedBatches: 0,
  } satisfies PublicPreKeyInventory
}

export function savePublicPreKeyInventory(
  deviceId: string,
  inventory: PublicPreKeyInventory,
) {
  localStorage.setItem(
    preKeyInventoryStorageKey(deviceId),
    JSON.stringify(inventory),
  )
}

export function forgetPublicPreKeyInventory(deviceId: string) {
  localStorage.removeItem(preKeyInventoryStorageKey(deviceId))
}

export async function createPublicDeviceRegistrationRequest() {
  const storedState = await getStoredLocalDeviceState()

  if (storedState) {
    savePublicDeviceRegistration(storedState.registration_request)
    return storedState.registration_request
  }

  const signingKeys = await crypto.subtle.generateKey(
    {
      name: "ECDSA",
      namedCurve: "P-256",
    },
    true,
    ["sign", "verify"],
  )

  const identityKeys = await crypto.subtle.generateKey(
    {
      name: "ECDH",
      namedCurve: "P-256",
    },
    true,
    ["deriveBits"],
  )

  const signedPreKeys = await crypto.subtle.generateKey(
    {
      name: "ECDH",
      namedCurve: "P-256",
    },
    true,
    ["deriveBits"],
  )

  const identityPublicKey = await crypto.subtle.exportKey(
    "raw",
    identityKeys.publicKey,
  )
  const signedPreKeyPublic = await crypto.subtle.exportKey(
    "raw",
    signedPreKeys.publicKey,
  )
  const signature = await crypto.subtle.sign(
    {
      name: "ECDSA",
      hash: "SHA-256",
    },
    signingKeys.privateKey,
    signedPreKeyPublic,
  )

  const request: RegisterDeviceRequest = {
    device_id: crypto.randomUUID(),
    device_name: browserDeviceName(),
    platform: "web",
    registration_id: randomRegistrationId(),
    identity_key_public: bytesToBase64(identityPublicKey),
    signed_prekey_id: randomSignedPreKeyId(),
    signed_prekey_public: bytesToBase64(signedPreKeyPublic),
    signed_prekey_signature: bytesToBase64(signature),
    key_algorithm: keyAlgorithm,
    key_bundle_version: 1,
  }

  savePublicDeviceRegistration(request)
  await saveStoredLocalDeviceState({
    registration_request: request,
    identity_agreement_private_jwk: await crypto.subtle.exportKey(
      "jwk",
      identityKeys.privateKey,
    ),
    identity_signing_private_jwk: await crypto.subtle.exportKey(
      "jwk",
      signingKeys.privateKey,
    ),
    signed_prekey_private_jwk: await crypto.subtle.exportKey(
      "jwk",
      signedPreKeys.privateKey,
    ),
    one_time_prekeys: [],
  })

  return request
}

export async function createOneTimePreKeyUploadRequest(input: {
  count: number
  startKeyId: number
}): Promise<UploadOneTimePreKeysRequest> {
  const oneTimePreKeys = []
  const storedPrivatePreKeys = []

  for (let index = 0; index < input.count; index += 1) {
    const keyId = input.startKeyId + index
    const preKey = await crypto.subtle.generateKey(
      {
        name: "ECDH",
        namedCurve: "P-256",
      },
      true,
      ["deriveBits"],
    )
    const publicKey = await crypto.subtle.exportKey("raw", preKey.publicKey)

    oneTimePreKeys.push({
      key_id: keyId,
      public_key: bytesToBase64(publicKey),
    })
    storedPrivatePreKeys.push({
      key_id: keyId,
      private_key_jwk: await crypto.subtle.exportKey("jwk", preKey.privateKey),
      public_key: bytesToBase64(publicKey),
      created_at: new Date().toISOString(),
    })
  }

  await addStoredOneTimePreKeys(storedPrivatePreKeys)

  return {
    one_time_prekeys: oneTimePreKeys,
  }
}

function randomBase64(byteLength: number) {
  const bytes = new Uint8Array(byteLength)
  crypto.getRandomValues(bytes)

  return bytesToBase64(bytes.buffer)
}

export function createDevDirectMessageRequest(input: {
  senderDeviceId: string
  claim: ClaimPreKeyBundlesResult
}): SendDirectMessageRequest {
  const envelopeNonce = () => randomBase64(24)
  const recipientEnvelopes: MessageKeyEnvelopeInput[] = input.claim.devices.map(
    (device) => ({
      recipient_device_id: device.device_id,
      protocol: "double_ratchet",
      session_reference: `dev-recipient-${device.device_id}`,
      wrapped_message_key: randomBase64(48),
      key_wrap_metadata: {
        mode: "dev-contract-placeholder",
        nonce: envelopeNonce(),
        one_time_prekey_id: device.one_time_prekey?.key_id ?? null,
      },
      envelope_version: 1,
    }),
  )

  return {
    recipient_user_id: input.claim.recipient_user_id,
    sender_device_id: input.senderDeviceId,
    client_message_id: crypto.randomUUID(),
    message_type: "text",
    encrypted_payload: randomBase64(96),
    encryption_metadata: {
      mode: "dev-contract-placeholder",
      algorithm: "not-production-e2ee",
      nonce: randomBase64(24),
      content_encoding: "opaque-random-bytes",
    },
    encryption_version: 1,
    reply_to_id: null,
    client_sent_at: new Date().toISOString(),
    envelopes: [
      {
        recipient_device_id: input.senderDeviceId,
        protocol: "device_sync",
        session_reference: `dev-sender-${input.senderDeviceId}`,
        wrapped_message_key: randomBase64(48),
        key_wrap_metadata: {
          mode: "dev-contract-placeholder",
          nonce: envelopeNonce(),
        },
        envelope_version: 1,
      },
      ...recipientEnvelopes,
    ],
  }
}

export async function createEncryptedDirectMessageRequest(input: {
  senderDeviceId: string
  claim: ClaimPreKeyBundlesResult
  body: string
}): Promise<SendDirectMessageRequest> {
  const clientMessageId = crypto.randomUUID()
  const messageType = "text"
  const encryptionVersion = 1
  const replyToId = null
  const clientSentAt = new Date().toISOString()
  const encrypted = await encryptMessageContent({
    type: messageType,
    body: input.body,
    sent_at: clientSentAt,
  }, messageAssociatedData({
    sender_device_id: input.senderDeviceId,
    client_message_id: clientMessageId,
    message_type: messageType,
    encryption_version: encryptionVersion,
    reply_to_id: replyToId,
    content_encoding: "utf8-json",
  }))
  const envelopeNonce = () => randomBase64(24)
  const recipientEnvelopes: MessageKeyEnvelopeInput[] = input.claim.devices.map(
    (device) => ({
      recipient_device_id: device.device_id,
      protocol: "double_ratchet",
      session_reference: `xchacha-recipient-${device.device_id}`,
      wrapped_message_key: encrypted.key,
      key_wrap_metadata: {
        algorithm: "double-ratchet-v1",
        note: "content-key-placeholder-until-session-wrap",
        nonce: envelopeNonce(),
        header_version: 1,
        one_time_prekey_id: device.one_time_prekey?.key_id ?? null,
      },
      envelope_version: 1,
    }),
  )

  return {
    recipient_user_id: input.claim.recipient_user_id,
    sender_device_id: input.senderDeviceId,
    client_message_id: clientMessageId,
    message_type: messageType,
    encrypted_payload: encrypted.ciphertext,
    encryption_metadata: {
      algorithm: encrypted.algorithm,
      nonce: encrypted.nonce,
      aad_version: encrypted.aad_version,
      content_encoding: encrypted.content_encoding,
    },
    encryption_version: encryptionVersion,
    reply_to_id: replyToId,
    client_sent_at: clientSentAt,
    envelopes: [
      {
        recipient_device_id: input.senderDeviceId,
        protocol: "device_sync",
        session_reference: `xchacha-sender-${input.senderDeviceId}`,
        wrapped_message_key: encrypted.key,
        key_wrap_metadata: {
          algorithm: encrypted.algorithm,
          note: "content-key-placeholder-until-device-sync-wrap",
          nonce: envelopeNonce(),
          header_version: 1,
        },
        envelope_version: 1,
      },
      ...recipientEnvelopes,
    ],
  }
}

export function addDevDeviceSyncEnvelopes(
  request: SendDirectMessageRequest,
  deviceIds: string[],
): SendDirectMessageRequest {
  const existingDeviceIds = new Set(
    request.envelopes.map((envelope) => envelope.recipient_device_id),
  )
  const extraEnvelopes = deviceIds
    .filter((deviceId) => !existingDeviceIds.has(deviceId))
    .map<MessageKeyEnvelopeInput>((deviceId) => ({
      recipient_device_id: deviceId,
      protocol: "device_sync",
      session_reference: `dev-sender-${deviceId}`,
      wrapped_message_key: randomBase64(48),
      key_wrap_metadata: {
        mode: "dev-contract-placeholder",
        nonce: randomBase64(24),
        retry_reason: "backend-reported-missing-envelope",
      },
      envelope_version: 1,
    }))

  if (!extraEnvelopes.length) {
    return request
  }

  return {
    ...request,
    envelopes: [
      ...request.envelopes,
      ...extraEnvelopes,
    ],
  }
}
