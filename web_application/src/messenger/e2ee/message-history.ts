import type { EncryptedHistoryMessage } from "@/messenger/api/messenger-api.types"

import { decryptMessageContent } from "./message-decryption"
import {
  messageAssociatedData,
  type PlaintextMessageContent,
} from "./message-encryption"
import {
  e2eeAadVersion,
  e2eeAeadAlgorithm,
  e2eeAeadVersion,
} from "./e2ee-codec"

export interface DecryptedHistoryMessage {
  messageId: string
  senderUserId: string
  createdAt: string
  content: PlaintextMessageContent
}

export async function decryptXChaCha20Poly1305HistoryMessage(
  message: EncryptedHistoryMessage,
) {
  const metadata = message.encryption_metadata
  const nonce = metadata.nonce
  const contentEncoding = metadata.content_encoding

  if (
    metadata.algorithm !== e2eeAeadAlgorithm
    || metadata.aad_version !== e2eeAadVersion
    || contentEncoding !== "utf8-json"
    || typeof nonce !== "string"
    || !message.device_envelope
  ) {
    return null
  }

  const content = await decryptMessageContent({
    ciphertext: message.encrypted_payload,
    key: message.device_envelope.wrapped_message_key,
    nonce,
    algorithm: e2eeAeadAlgorithm,
    version: e2eeAeadVersion,
    aad_version: e2eeAadVersion,
    content_encoding: "utf8-json",
  }, messageAssociatedData({
    sender_device_id: message.sender_device_id,
    client_message_id: message.client_message_id,
    message_type: message.message_type,
    encryption_version: message.encryption_version,
    reply_to_id: message.reply_to_id,
    content_encoding: "utf8-json",
  }))

  return {
    messageId: message.id,
    senderUserId: message.sender_user_id,
    createdAt: message.created_at,
    content,
  } satisfies DecryptedHistoryMessage
}

export async function decryptXChaCha20Poly1305History(
  messages: EncryptedHistoryMessage[],
) {
  const decrypted = await Promise.all(
    messages.map((message) =>
      decryptXChaCha20Poly1305HistoryMessage(message),
    ),
  )

  return decrypted.filter((message): message is DecryptedHistoryMessage =>
    Boolean(message),
  )
}
