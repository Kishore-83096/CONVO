import { xchacha20poly1305 } from "@noble/ciphers/chacha.js"

import type { Base64String } from "@/messenger/api/messenger-api.types"

export const e2eeAeadAlgorithm = "xchacha20poly1305-ietf"
export const e2eeAeadVersion = 1
export const e2eeNonceByteLength = 24
export const e2eeKeyByteLength = 32
export const e2eeAadVersion = 1

export interface E2EEEncryptedBytes {
  ciphertext: Base64String
  key: Base64String
  nonce: Base64String
  algorithm: typeof e2eeAeadAlgorithm
  version: typeof e2eeAeadVersion
  aad_version: typeof e2eeAadVersion
}

export function bytesToBase64(bytes: ArrayBuffer | Uint8Array): Base64String {
  const values = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  let binary = ""

  for (const value of values) {
    binary += String.fromCharCode(value)
  }

  return btoa(binary)
}

export function base64ToBytes(value: Base64String): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  return bytes
}

export function randomBytes(byteLength: number) {
  const bytes = new Uint8Array(byteLength)
  crypto.getRandomValues(bytes)

  return bytes
}

export function encodeJson(value: unknown) {
  return new TextEncoder().encode(JSON.stringify(value))
}

export function decodeJson<T>(bytes: ArrayBuffer | Uint8Array): T {
  const values = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)

  return JSON.parse(new TextDecoder().decode(values)) as T
}

export function encodeAssociatedData(value: unknown) {
  return encodeJson(value)
}

export function generateContentKey() {
  return randomBytes(e2eeKeyByteLength)
}

function assertByteLength(bytes: Uint8Array, expected: number, label: string) {
  if (bytes.byteLength !== expected) {
    throw new Error(`${label} must be ${expected} bytes.`)
  }
}

export async function encryptBytes(
  plaintext: Uint8Array,
  associatedData = new Uint8Array(),
): Promise<E2EEEncryptedBytes> {
  const key = generateContentKey()
  const nonce = randomBytes(e2eeNonceByteLength)
  const ciphertext = xchacha20poly1305(
    key,
    nonce,
    associatedData,
  ).encrypt(plaintext)

  return {
    ciphertext: bytesToBase64(ciphertext),
    key: bytesToBase64(key),
    nonce: bytesToBase64(nonce),
    algorithm: e2eeAeadAlgorithm,
    version: e2eeAeadVersion,
    aad_version: e2eeAadVersion,
  }
}

export async function decryptBytes(
  input: E2EEEncryptedBytes,
  associatedData = new Uint8Array(),
) {
  if (
    input.algorithm !== e2eeAeadAlgorithm
    || input.version !== e2eeAeadVersion
    || input.aad_version !== e2eeAadVersion
  ) {
    throw new Error("Unsupported encrypted payload format.")
  }

  const key = base64ToBytes(input.key)
  const nonce = base64ToBytes(input.nonce)

  assertByteLength(key, e2eeKeyByteLength, "Content key")
  assertByteLength(nonce, e2eeNonceByteLength, "Nonce")

  return xchacha20poly1305(
    key,
    nonce,
    associatedData,
  ).decrypt(base64ToBytes(input.ciphertext))
}
