import type { ReactNode } from "react";

import { Button } from "./Button";

type WarningModalProps = {
  busyLabel?: string;
  cancelLabel?: string;
  children?: ReactNode;
  confirmLabel?: string;
  description: string;
  isBusy?: boolean;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
};

export function WarningModal({
  busyLabel = "Deleting...",
  cancelLabel = "Cancel",
  children,
  confirmLabel = "Delete",
  description,
  isBusy = false,
  isOpen,
  onClose,
  onConfirm,
  title,
}: WarningModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="warning-modal-backdrop" role="presentation">
      <section
        aria-modal="true"
        className="warning-modal"
        role="dialog"
        aria-labelledby="warning-modal-title"
      >
        <div className="warning-modal__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <path d="M12 8V13" />
            <path d="M12 17H12.01" />
            <path d="M10.3 4.5L2.8 18A2 2 0 0 0 4.5 21H19.5A2 2 0 0 0 21.2 18L13.7 4.5A2 2 0 0 0 10.3 4.5Z" />
          </svg>
        </div>

        <div className="warning-modal__copy">
          <h2 id="warning-modal-title">{title}</h2>
          <p>{description}</p>
        </div>

        {children ? (
          <div className="warning-modal__content">{children}</div>
        ) : null}

        <div className="warning-modal__actions">
          <Button
            disabled={isBusy}
            onClick={onClose}
            type="button"
            variant="secondary"
          >
            {cancelLabel}
          </Button>
          <Button
            disabled={isBusy}
            onClick={() => void onConfirm()}
            type="button"
            variant="danger"
          >
            {isBusy ? busyLabel : confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  );
}
