import {
  decryptBytes,
  decodeJson,
  type E2EEEncryptedBytes,
} from "./e2ee-codec"
import type { PlaintextMessageContent } from "./message-encryption"

export interface DecryptableMessageContent extends E2EEEncryptedBytes {
  content_encoding: "utf8-json"
}

export async function decryptMessageContent(
  input: DecryptableMessageContent,
  associatedData = new Uint8Array(),
): Promise<PlaintextMessageContent> {
  return decodeJson<PlaintextMessageContent>(
    await decryptBytes(input, associatedData),
  )
}
