import {
  decryptBytes,
  type E2EEEncryptedBytes,
} from "./e2ee-codec"
import { attachmentAssociatedData } from "./attachment-encryption"
import type { Base64String } from "@/messenger/api/messenger-api.types"

export interface DecryptableAttachmentContent extends E2EEEncryptedBytes {
  file_name: string
  mime_type: string
  size: number
  sha256: Base64String
}

export async function decryptAttachmentContent(
  input: DecryptableAttachmentContent,
) {
  const plaintext = await decryptBytes(
    input,
    attachmentAssociatedData({
      file_name: input.file_name,
      mime_type: input.mime_type,
      size: input.size,
      sha256: input.sha256,
    }),
  )

  return new File(
    [plaintext],
    input.file_name,
    {
      type: input.mime_type,
    },
  )
}
