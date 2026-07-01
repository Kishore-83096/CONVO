import { useState } from "react";

import { WarningModal } from "../../../shared/ui/WarningModal";
import { useDeleteMyProfileBasic } from "../hooks";

type BasicProfileDeletePanelProps = {
  onCancel?: () => void;
  onDeleted?: () => void;
};

export function BasicProfileDeletePanel({
  onCancel,
  onDeleted,
}: BasicProfileDeletePanelProps) {
  const [isWarningOpen, setIsWarningOpen] = useState(true);
  const deleteBasicProfile = useDeleteMyProfileBasic();
  const isDisabled = deleteBasicProfile.isPending;

  function closeWarning() {
    setIsWarningOpen(false);
    onCancel?.();
  }

  async function handleDeleteBasicProfile() {
    const result = await deleteBasicProfile.mutateAsync();

    if (result.ok) {
      setIsWarningOpen(false);
      onDeleted?.();
    }
  }

  return (
    <WarningModal
      confirmLabel="Delete basic profile"
      description="This removes your bio, date of birth, gender, occupation, and website from your profile."
      isBusy={isDisabled}
      isOpen={isWarningOpen}
      onClose={closeWarning}
      onConfirm={handleDeleteBasicProfile}
      title="Delete basic profile?"
    >
      {deleteBasicProfile.data && !deleteBasicProfile.data.ok ? (
        <div className="auth-error" role="alert">
          {deleteBasicProfile.data.message}
        </div>
      ) : null}

      {deleteBasicProfile.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Basic profile deleted.</strong>
          <p>The profile sections should refresh automatically.</p>
        </div>
      ) : null}

      {deleteBasicProfile.isError ? (
        <div className="auth-error" role="alert">
          Basic profile delete failed before the server returned a response.
        </div>
      ) : null}
    </WarningModal>
  );
}
