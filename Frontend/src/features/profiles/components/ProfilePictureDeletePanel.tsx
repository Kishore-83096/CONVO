import { useState } from "react";

import { WarningModal } from "../../../shared/ui/WarningModal";
import { useDeleteMyProfilePicture } from "../hooks";

type ProfilePictureDeletePanelProps = {
  onCancel?: () => void;
  onDeleted?: () => void;
};

export function ProfilePictureDeletePanel({
  onCancel,
  onDeleted,
}: ProfilePictureDeletePanelProps) {
  const [isWarningOpen, setIsWarningOpen] = useState(true);
  const deletePicture = useDeleteMyProfilePicture();
  const isDisabled = deletePicture.isPending;

  function closeWarning() {
    setIsWarningOpen(false);
    onCancel?.();
  }

  async function handleDeletePicture() {
    const result = await deletePicture.mutateAsync();

    if (result.ok) {
      setIsWarningOpen(false);
      onDeleted?.();
    }
  }

  return (
    <WarningModal
      confirmLabel="Delete picture"
      description="This removes the current profile picture from your account."
      isBusy={isDisabled}
      isOpen={isWarningOpen}
      onClose={closeWarning}
      onConfirm={handleDeletePicture}
      title="Delete profile picture?"
    >
      {deletePicture.data && !deletePicture.data.ok ? (
        <div className="auth-error" role="alert">
          {deletePicture.data.message}
        </div>
      ) : null}

      {deletePicture.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Profile picture deleted.</strong>
          <p>The profile picture should refresh automatically.</p>
        </div>
      ) : null}

      {deletePicture.isError ? (
        <div className="auth-error" role="alert">
          Profile picture delete failed before the server returned a response.
        </div>
      ) : null}
    </WarningModal>
  );
}
