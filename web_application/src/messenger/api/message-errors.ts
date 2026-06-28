const uuidPattern =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi

export function extractMissingEnvelopeDeviceIds(message: string) {
  if (!message.includes("Encrypted envelopes are missing")) {
    return []
  }

  return Array.from(new Set(message.match(uuidPattern) ?? []))
}
