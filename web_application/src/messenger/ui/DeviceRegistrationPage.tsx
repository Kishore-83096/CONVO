import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { RefreshCcw, ShieldCheck, X } from "lucide-react"
import { useNavigate } from "react-router"

import {
  registerMessengerDevice,
} from "@/messenger/api/devices.api"
import { getEncryptedHistory } from "@/messenger/api/history.api"
import { MessengerApiError } from "@/messenger/api/messenger-client"
import { extractMissingEnvelopeDeviceIds } from "@/messenger/api/message-errors"
import { sendDirectMessage } from "@/messenger/api/messages.api"
import { claimPreKeyBundles } from "@/messenger/api/prekey-bundles.api"
import { uploadOneTimePreKeys } from "@/messenger/api/prekeys.api"
import type {
  ClaimPreKeyBundlesResult,
  EncryptedHistoryResult,
  RegisterDeviceRequest,
  RegisterDeviceResult,
  SendDirectMessageResult,
  UploadOneTimePreKeysResult,
} from "@/messenger/api/messenger-api.types"
import {
  addDevDeviceSyncEnvelopes,
  createDevDirectMessageRequest,
  createOneTimePreKeyUploadRequest,
  createPublicDeviceRegistrationRequest,
  forgetLocalDeviceIdentity,
  forgetPublicPreKeyInventory,
  getPublicPreKeyInventory,
  getStoredPublicDeviceRegistration,
  savePublicDeviceRegistration,
  savePublicPreKeyInventory,
} from "@/messenger/crypto/device-registration"

interface DeviceRegistrationPageProps {
  accessToken: string
  onClose: () => void
  storageKey: string
}

const preKeyBatchSize = 20

type E2EETab = "device" | "prekeys" | "recipient" | "test" | "advanced"

const e2eeTabs: { id: E2EETab; label: string }[] = [
  { id: "device", label: "Device" },
  { id: "prekeys", label: "Prekeys" },
  { id: "recipient", label: "Recipient" },
  { id: "test", label: "Test" },
  { id: "advanced", label: "Advanced" },
]

function savedE2EETab(storageKey: string): E2EETab {
  const tab = localStorage.getItem(storageKey)
  const validTabs = e2eeTabs.map((e2eeTab) => e2eeTab.id)

  return validTabs.includes(tab as E2EETab)
    ? (tab as E2EETab)
    : "device"
}

function shortValue(value: string) {
  return `${value.slice(0, 10)}...${value.slice(-8)}`
}

function DeviceRegistrationPage({
  accessToken,
  onClose,
  storageKey,
}: DeviceRegistrationPageProps) {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<E2EETab>(() =>
    savedE2EETab(storageKey),
  )
  const [request, setRequest] = useState<RegisterDeviceRequest | null>(null)
  const [result, setResult] = useState<RegisterDeviceResult | null>(null)
  const [preKeyResult, setPreKeyResult] =
    useState<UploadOneTimePreKeysResult | null>(null)
  const [recipientUserId, setRecipientUserId] = useState("")
  const [claimResult, setClaimResult] = useState<ClaimPreKeyBundlesResult | null>(null)
  const [sendResult, setSendResult] = useState<SendDirectMessageResult | null>(null)
  const [historyResult, setHistoryResult] = useState<EncryptedHistoryResult | null>(null)
  const [statusMessage, setStatusMessage] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [isClaimingBundles, setIsClaimingBundles] = useState(false)
  const [isFetchingHistory, setIsFetchingHistory] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [isUploadingPreKeys, setIsUploadingPreKeys] = useState(false)
  const [isRegistering, setIsRegistering] = useState(false)
  const didAutoBootstrap = useRef(false)

  const isBusy =
    isGenerating
    || isRegistering
    || isUploadingPreKeys
    || isClaimingBundles
    || isFetchingHistory
    || isSendingMessage
  const canRefresh = Boolean(request) && !isBusy
  const canUploadPreKeys = Boolean(result) && !isBusy
  const canClaimBundles = Boolean(recipientUserId.trim()) && !isBusy
  const canSendContractMessage = Boolean(result && claimResult) && !isBusy
  const canFetchHistory = Boolean(result && sendResult) && !isBusy

  const keySummary = useMemo(() => {
    if (!request) {
      return []
    }

    return [
      ["Device ID", request.device_id],
      ["Registration ID", String(request.registration_id)],
      ["Identity public key", shortValue(request.identity_key_public)],
      ["Signed prekey", shortValue(request.signed_prekey_public)],
      ["Algorithm", request.key_algorithm],
    ]
  }, [request])

  const uploadPreKeyBatch = useCallback(async (
    deviceId: string,
    options?: { automatic?: boolean },
  ) => {
    setIsUploadingPreKeys(true)
    setErrorMessage("")

    try {
      const inventory = getPublicPreKeyInventory(deviceId)
      const uploadRequest = await createOneTimePreKeyUploadRequest({
        count: preKeyBatchSize,
        startKeyId: inventory.nextKeyId,
      })
      const response = await uploadOneTimePreKeys(
        deviceId,
        uploadRequest,
        accessToken,
      )

      savePublicPreKeyInventory(deviceId, {
        nextKeyId: inventory.nextKeyId + preKeyBatchSize,
        uploadedBatches: inventory.uploadedBatches + 1,
      })
      setPreKeyResult(response.data)
      setStatusMessage(
        options?.automatic
          ? `Device ready. Initial prekeys uploaded: ${response.data.prekeys_created}.`
          : response.message,
      )
    } catch (error) {
      if (error instanceof MessengerApiError && error.status === 401) {
        navigate("/", { replace: true })
        return
      }

      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to upload one-time prekeys.",
      )
    } finally {
      setIsUploadingPreKeys(false)
    }
  }, [accessToken, navigate])

  const ensureInitialPreKeys = useCallback(async (deviceId: string) => {
    const inventory = getPublicPreKeyInventory(deviceId)

    if (inventory.uploadedBatches > 0) {
      return
    }

    await uploadPreKeyBatch(deviceId, { automatic: true })
  }, [uploadPreKeyBatch])

  const submitRegistration = useCallback(async (
    registrationRequest: RegisterDeviceRequest,
    options?: { automatic?: boolean },
  ) => {
    setIsRegistering(true)
    setErrorMessage("")
    setStatusMessage("")

    try {
      const response = await registerMessengerDevice(
        registrationRequest,
        accessToken,
      )
      savePublicDeviceRegistration(registrationRequest)
      setRequest(registrationRequest)
      setResult(response.data)
      setStatusMessage(
        options?.automatic
          ? `Device registration checked: ${response.message}`
          : response.message,
      )
      await ensureInitialPreKeys(response.data.device_id)
    } catch (error) {
      if (error instanceof MessengerApiError && error.status === 401) {
        navigate("/", { replace: true })
        return
      }

      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to register this browser device.",
      )
    } finally {
      setIsRegistering(false)
    }
  }, [accessToken, ensureInitialPreKeys, navigate])

  const bootstrapDevice = useCallback(async () => {
    setIsGenerating(true)
    setErrorMessage("")
    setStatusMessage("Checking this browser's E2EE device registration.")

    try {
      const storedRequest =
        getStoredPublicDeviceRegistration()
        ?? await createPublicDeviceRegistrationRequest()

      setRequest(storedRequest)
      await submitRegistration(storedRequest, { automatic: true })
    } catch {
      setErrorMessage("Unable to prepare this browser device registration.")
    } finally {
      setIsGenerating(false)
    }
  }, [submitRegistration])

  useEffect(() => {
    if (didAutoBootstrap.current) {
      return
    }

    didAutoBootstrap.current = true
    void bootstrapDevice()
  }, [bootstrapDevice])

  useEffect(() => {
    localStorage.setItem(storageKey, activeTab)
  }, [activeTab, storageKey])

  const resetDeviceIdentity = async () => {
    const confirmed = window.confirm(
      "Create a new local E2EE device identity for this browser?",
    )

    if (!confirmed) {
      return
    }

    await forgetLocalDeviceIdentity()
    setRequest(null)
    setResult(null)
    if (result?.device_id) {
      forgetPublicPreKeyInventory(result.device_id)
    }
    setPreKeyResult(null)
    setStatusMessage("")
    setErrorMessage("")
    setIsGenerating(true)

    try {
      const nextRequest = await createPublicDeviceRegistrationRequest()
      await submitRegistration(nextRequest)
      setStatusMessage("New local device identity registered.")
    } catch {
      setErrorMessage("Unable to create a new local device identity.")
    } finally {
      setIsGenerating(false)
    }
  }

  const refreshRegistration = async () => {
    if (!request) {
      await bootstrapDevice()
      return
    }

    await submitRegistration(request)
  }

  const replenishPreKeys = async () => {
    if (!result) {
      return
    }

    await uploadPreKeyBatch(result.device_id)
  }

  const claimRecipientBundles = async () => {
    const normalizedRecipientUserId = recipientUserId.trim()

    if (!normalizedRecipientUserId) {
      return
    }

    setIsClaimingBundles(true)
    setErrorMessage("")
    setStatusMessage("")

    try {
      const response = await claimPreKeyBundles(
        {
          recipient_user_id: normalizedRecipientUserId,
        },
        accessToken,
      )

      setClaimResult(response.data)
      setSendResult(null)
      setHistoryResult(null)
      setStatusMessage(response.message)
    } catch (error) {
      if (error instanceof MessengerApiError && error.status === 401) {
        navigate("/", { replace: true })
        return
      }

      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to claim recipient prekey bundles.",
      )
    } finally {
      setIsClaimingBundles(false)
    }
  }

  const sendContractMessage = async () => {
    if (!result || !claimResult) {
      return
    }

    setIsSendingMessage(true)
    setErrorMessage("")
    setStatusMessage("")

    try {
      let requestPayload = createDevDirectMessageRequest({
        senderDeviceId: result.device_id,
        claim: claimResult,
      })
      let response

      try {
        response = await sendDirectMessage(requestPayload, accessToken)
      } catch (error) {
        const missingDeviceIds =
          error instanceof MessengerApiError
            ? extractMissingEnvelopeDeviceIds(error.message)
            : []

        if (!missingDeviceIds.length) {
          throw error
        }

        requestPayload = addDevDeviceSyncEnvelopes(
          requestPayload,
          missingDeviceIds,
        )
        response = await sendDirectMessage(requestPayload, accessToken)
      }

      setSendResult(response.data)
      setHistoryResult(null)
      setStatusMessage(response.message)
    } catch (error) {
      if (error instanceof MessengerApiError && error.status === 401) {
        navigate("/", { replace: true })
        return
      }

      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to send the direct-message contract test.",
      )
    } finally {
      setIsSendingMessage(false)
    }
  }

  const fetchContractHistory = async () => {
    if (!result || !sendResult) {
      return
    }

    setIsFetchingHistory(true)
    setErrorMessage("")
    setStatusMessage("")

    try {
      const response = await getEncryptedHistory(
        sendResult.room_id,
        result.device_id,
        accessToken,
      )

      setHistoryResult(response.data)
      setStatusMessage(response.message)
    } catch (error) {
      if (error instanceof MessengerApiError && error.status === 401) {
        navigate("/", { replace: true })
        return
      }

      setErrorMessage(
        error instanceof MessengerApiError
          ? error.message
          : "Unable to fetch encrypted message history.",
      )
    } finally {
      setIsFetchingHistory(false)
    }
  }

  return (
    <section className="main-view workspace-view active">
      <header className="workspace-header messenger-device-header">
        <div className="workspace-title-row">
          <div className="workspace-title-copy">
            <span className="section-kicker">Messenger API</span>
            <h2>E2EE settings</h2>
            <p>
              Manage this browser's encrypted messaging setup.
            </p>
          </div>
          <button
            className="main-close-button"
            type="button"
            aria-label="Close device registration"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </div>

        <nav className="workspace-tabs" aria-label="E2EE tabs">
          {e2eeTabs.map((tab) => (
            <button
              className={`workspace-tab ${activeTab === tab.id ? "active" : ""}`}
              key={tab.id}
              type="button"
              onClick={() => {
                setActiveTab(tab.id)
                setStatusMessage("")
                setErrorMessage("")
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="workspace-content messenger-device-content">
        <section className={`workspace-panel ${activeTab === "device" ? "active" : ""}`}>
          <div className="messenger-device-status">
            <span className="messenger-device-status-icon">
              <ShieldCheck aria-hidden="true" />
            </span>
            <div>
              <strong>
                {isGenerating || isRegistering
                  ? "Checking device"
                  : result
                    ? "Device registered"
                    : "Device setup pending"}
              </strong>
              <p>
                This browser needs a registered device bundle before encrypted
                messages can work.
              </p>
            </div>
          </div>

          <div className="messenger-device-actions">
            <button
              className="secondary-action-button"
              type="button"
              disabled={!canRefresh}
              onClick={() => void refreshRegistration()}
            >
              <RefreshCcw aria-hidden="true" />
              <span>{isRegistering ? "Checking" : "Refresh status"}</span>
            </button>
          </div>

          {request ? (
            <dl className="messenger-device-details">
              {keySummary.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="profile-message">
              No browser device bundle has been generated yet.
            </p>
          )}

          {result ? (
            <dl className="messenger-device-details messenger-device-result">
              <div>
                <dt>Server device ID</dt>
                <dd>{result.device_id}</dd>
              </div>
              <div>
                <dt>Messenger user ID</dt>
                <dd>{result.user_id}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{result.device_created ? "Yes" : "Already existed"}</dd>
              </div>
              <div>
                <dt>Prekeys created</dt>
                <dd>{result.prekeys_created}</dd>
              </div>
            </dl>
          ) : null}
        </section>

        <section className={`workspace-panel ${activeTab === "prekeys" ? "active" : ""}`}>
          {result ? (
            <div className="messenger-device-prekeys">
              <div>
                <strong>One-time prekeys</strong>
                <p>
                  Upload public prekeys so other devices can start encrypted
                  sessions with this browser.
                </p>
              </div>
              <button
                className="primary-action-button"
                type="button"
                disabled={!canUploadPreKeys}
                onClick={() => void replenishPreKeys()}
              >
                {isUploadingPreKeys ? "Uploading" : "Replenish prekeys"}
              </button>
              {preKeyResult ? (
                <dl className="messenger-device-details messenger-device-result">
                  <div>
                    <dt>Latest created</dt>
                    <dd>{preKeyResult.prekeys_created}</dd>
                  </div>
                  <div>
                    <dt>Latest unchanged</dt>
                    <dd>{preKeyResult.prekeys_unchanged}</dd>
                  </div>
                </dl>
              ) : null}
            </div>
          ) : (
            <p className="profile-message">
              Register this device before replenishing prekeys.
            </p>
          )}
        </section>

        <section className={`workspace-panel ${activeTab === "recipient" ? "active" : ""}`}>
          {result ? (
            <div className="messenger-device-prekeys">
              <div>
                <strong>Recipient setup</strong>
                <p>
                  Claim a recipient's public device bundles before creating a new
                  encrypted session. This can consume one recipient one-time prekey.
                </p>
              </div>
              <div className="messenger-device-claim-form">
                <label className="form-field" htmlFor="recipientUserId">
                  <span>Recipient user ID</span>
                  <input
                    id="recipientUserId"
                    type="text"
                    inputMode="numeric"
                    value={recipientUserId}
                    placeholder="For example, 2"
                    onChange={(event) => {
                      setRecipientUserId(event.target.value)
                      setClaimResult(null)
                    }}
                  />
                </label>
                <button
                  className="primary-action-button"
                  type="button"
                  disabled={!canClaimBundles}
                  onClick={() => void claimRecipientBundles()}
                >
                  {isClaimingBundles ? "Claiming" : "Claim prekey bundles"}
                </button>
              </div>
              {claimResult ? (
                <dl className="messenger-device-details messenger-device-result">
                  <div>
                    <dt>Recipient</dt>
                    <dd>{claimResult.recipient_user_id}</dd>
                  </div>
                  <div>
                    <dt>Devices found</dt>
                    <dd>{claimResult.device_count}</dd>
                  </div>
                  <div>
                    <dt>One-time prekeys</dt>
                    <dd>
                      {
                        claimResult.devices.filter(
                          (device) => device.one_time_prekey,
                        ).length
                      }{" "}
                      claimed
                    </dd>
                  </div>
                  <div>
                    <dt>First device</dt>
                    <dd>
                      {claimResult.devices[0]
                        ? claimResult.devices[0].device_id
                        : "None"}
                    </dd>
                  </div>
                </dl>
              ) : null}
            </div>
          ) : (
            <p className="profile-message">
              Register this device before claiming recipient bundles.
            </p>
          )}
        </section>

        <section className={`workspace-panel ${activeTab === "test" ? "active" : ""}`}>
          {result && claimResult ? (
            <div className="messenger-device-prekeys">
              <div>
                <strong>Direct message contract test</strong>
                <p>
                  Submit an opaque placeholder ciphertext and device envelopes
                  to verify the backend direct-message contract.
                </p>
              </div>
              <button
                className="primary-action-button"
                type="button"
                disabled={!canSendContractMessage}
                onClick={() => void sendContractMessage()}
              >
                {isSendingMessage ? "Sending" : "Send contract test message"}
              </button>
              {sendResult ? (
                <dl className="messenger-device-details messenger-device-result">
                  <div>
                    <dt>Room ID</dt>
                    <dd>{sendResult.room_id}</dd>
                  </div>
                  <div>
                    <dt>Message ID</dt>
                    <dd>{sendResult.message_id}</dd>
                  </div>
                  <div>
                    <dt>Message created</dt>
                    <dd>{sendResult.message_created ? "Yes" : "Already existed"}</dd>
                  </div>
                  <div>
                    <dt>Envelope count</dt>
                    <dd>{sendResult.envelope_count}</dd>
                  </div>
                </dl>
              ) : null}
              {sendResult ? (
                <button
                  className="secondary-action-button"
                  type="button"
                  disabled={!canFetchHistory}
                  onClick={() => void fetchContractHistory()}
                >
                  {isFetchingHistory ? "Fetching history" : "Fetch history"}
                </button>
              ) : null}
              {historyResult ? (
                <dl className="messenger-device-details messenger-device-result">
                  <div>
                    <dt>History messages</dt>
                    <dd>{historyResult.messages.length}</dd>
                  </div>
                  <div>
                    <dt>History device</dt>
                    <dd>{historyResult.device_id}</dd>
                  </div>
                  <div>
                    <dt>First envelope device</dt>
                    <dd>
                      {historyResult.messages[0]?.device_envelope?.recipient_device_id
                        ?? "None"}
                    </dd>
                  </div>
                  <div>
                    <dt>Next page</dt>
                    <dd>{historyResult.next ? "Available" : "None"}</dd>
                  </div>
                </dl>
              ) : null}
            </div>
          ) : (
            <p className="profile-message">
              Register this device and claim recipient bundles before running
              the contract test.
            </p>
          )}
        </section>

        {statusMessage ? <p className="profile-message">{statusMessage}</p> : null}
        {errorMessage ? <p className="profile-error">{errorMessage}</p> : null}

        <section className={`workspace-panel ${activeTab === "advanced" ? "active" : ""}`}>
          <div className="messenger-device-advanced">
            <div className="messenger-device-advanced-panel">
              <p>
                Reset only when this browser needs a fresh local E2EE identity.
                Existing encrypted history may not be decryptable by the new
                identity.
              </p>
              <button
                className="danger-action-button"
                type="button"
                disabled={isBusy}
                onClick={() => void resetDeviceIdentity()}
              >
                Reset local device identity
              </button>
            </div>
          </div>
        </section>
      </div>
    </section>
  )
}

export default DeviceRegistrationPage
