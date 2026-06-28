import type { MessageType } from "@/messenger/api/messenger-api.types"

import {
  encodeAssociatedData,
  encryptBytes,
  encodeJson,
  e2eeAadVersion,
  type E2EEEncryptedBytes,
} from "./e2ee-codec"

export interface PlaintextMessageContent {
  type: MessageType
  body: string
  sent_at: string
}

export interface EncryptedMessageContent extends E2EEEncryptedBytes {
  content_encoding: "utf8-json"
}

export interface MessageAssociatedDataInput {
  sender_device_id: string
  client_message_id: string
  message_type: MessageType
  encryption_version: number
  reply_to_id: string | null
  content_encoding: "utf8-json"
}

export function messageAssociatedData(input: MessageAssociatedDataInput) {
  return encodeAssociatedData({
    aad_version: e2eeAadVersion,
    sender_device_id: input.sender_device_id,
    client_message_id: input.client_message_id,
    message_type: input.message_type,
    encryption_version: input.encryption_version,
    reply_to_id: input.reply_to_id,
    content_encoding: input.content_encoding,
  })
}

export async function encryptMessageContent(
  content: PlaintextMessageContent,
  associatedData = new Uint8Array(),
): Promise<EncryptedMessageContent> {
  return {
    ...await encryptBytes(encodeJson(content), associatedData),
    content_encoding: "utf8-json",
  }
}
