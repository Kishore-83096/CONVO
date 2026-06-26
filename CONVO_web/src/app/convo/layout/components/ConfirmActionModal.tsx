import { useId } from "react"
import { AlertTriangle, X } from "lucide-react"

interface ConfirmActionModalProps {
  cancelLabel?: string
  confirmLabel: string
  description: string
  isBusy?: boolean
  isOpen: boolean
  title: string
  tone?: "danger" | "warning"
  onCancel: () => void
  onConfirm: () => void
}

function ConfirmActionModal({
  cancelLabel = "Cancel",
  confirmLabel,
  description,
  isBusy = false,
  isOpen,
  title,
  tone = "warning",
  onCancel,
  onConfirm,
}: ConfirmActionModalProps) {
  const titleId = useId()
  const descriptionId = useId()

  if (!isOpen) {
    return null
  }

  return (
    <div className="confirm-modal-backdrop" role="presentation">
      <section
        className={`confirm-modal confirm-modal--${tone}`}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        aria-modal="true"
        role="dialog"
      >
        <button
          className="confirm-modal-close"
          type="button"
          aria-label="Close confirmation"
          disabled={isBusy}
          onClick={onCancel}
        >
          <X aria-hidden="true" />
        </button>

        <span className="confirm-modal-icon" aria-hidden="true">
          <AlertTriangle />
        </span>

        <div className="confirm-modal-copy">
          <h2 id={titleId}>{title}</h2>
          <p id={descriptionId}>{description}</p>
        </div>

        <div className="confirm-modal-actions">
          <button
            className="secondary-action-button"
            type="button"
            disabled={isBusy}
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            className="danger-action-button"
            type="button"
            disabled={isBusy}
            onClick={onConfirm}
          >
            {isBusy ? "Please wait..." : confirmLabel}
          </button>
        </div>
      </section>
    </div>
  )
}

export default ConfirmActionModal
