import { useId, type ReactNode } from "react";

type FormModalProps = {
  children: ReactNode;
  description?: string;
  isOpen: boolean;
  onClose: () => void;
  title: string;
};

export function FormModal({
  children,
  description,
  isOpen,
  onClose,
  title,
}: FormModalProps) {
  const titleId = useId();

  if (!isOpen) {
    return null;
  }

  return (
    <div className="form-modal-backdrop" role="presentation">
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="form-modal"
        role="dialog"
      >
        <header className="form-modal__header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>

          <button
            aria-label="Close"
            className="form-modal__close motion-button-switch"
            onClick={onClose}
            type="button"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M18 6L6 18" />
              <path d="M6 6L18 18" />
            </svg>
          </button>
        </header>

        <div className="form-modal__body">{children}</div>
      </section>
    </div>
  );
}
