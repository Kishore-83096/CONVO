import type { Base64String } from "@/messenger/api/messenger-api.types"

import {
  bytesToBase64,
  encodeAssociatedData,
  encryptBytes,
  e2eeAadVersion,
  type E2EEEncryptedBytes,
} from "./e2ee-codec"

export interface AttachmentEncryptionInput {
  file: File | Blob
  fileName?: string
  mimeType?: string
}

export interface EncryptedAttachmentContent extends E2EEEncryptedBytes {
  file_name: string
  mime_type: string
  size: number
  sha256: Base64String
  aad_version: typeof e2eeAadVersion
}

export function attachmentAssociatedData(input: {
  file_name: string
  mime_type: string
  size: number
  sha256: Base64String
}) {
  return encodeAssociatedData({
    aad_version: e2eeAadVersion,
    file_name: input.file_name,
    mime_type: input.mime_type,
    size: input.size,
    sha256: input.sha256,
  })
}

export async function encryptAttachmentContent(
  input: AttachmentEncryptionInput,
): Promise<EncryptedAttachmentContent> {
  const plaintext = await input.file.arrayBuffer()
  const digest = await crypto.subtle.digest("SHA-256", plaintext)
  const fileName =
    input.fileName
    ?? (input.file instanceof File ? input.file.name : "encrypted-attachment")
  const mimeType = input.mimeType ?? input.file.type
  const sha256 = bytesToBase64(digest)
  const encrypted = await encryptBytes(
    new Uint8Array(plaintext),
    attachmentAssociatedData({
      file_name: fileName,
      mime_type: mimeType,
      size: input.file.size,
      sha256,
    }),
  )

  return {
    ...encrypted,
    file_name: fileName,
    mime_type: mimeType,
    size: input.file.size,
    sha256,
    aad_version: e2eeAadVersion,
  }
}
