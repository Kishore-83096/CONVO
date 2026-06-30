import {
  type ReactNode,
  useEffect,
} from "react";

interface DialogProps {
  open: boolean;

  title: string;

  children: ReactNode;

  onClose(): void;

  footer?: ReactNode;

  width?: number;
}

export function Dialog({
  open,
  title,
  children,
  onClose,
  footer,
  width = 480,
}: DialogProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      document.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="ui-dialog-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="ui-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        style={{
          maxWidth: `${width}px`,
        }}
        onClick={(event) =>
          event.stopPropagation()
        }
      >
        <header className="ui-dialog__header">
          <h2 id="dialog-title">
            {title}
          </h2>

          <button
            type="button"
            className="ui-dialog__close"
            onClick={onClose}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </header>

        <div className="ui-dialog__body">
          {children}
        </div>

        {footer && (
          <footer className="ui-dialog__footer">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}