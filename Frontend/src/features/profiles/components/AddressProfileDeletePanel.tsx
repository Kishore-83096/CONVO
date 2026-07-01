import { useState } from "react";

import { WarningModal } from "../../../shared/ui/WarningModal";
import { useDeleteMyProfileAddress } from "../hooks";

type AddressProfileDeletePanelProps = {
  onCancel?: () => void;
  onDeleted?: () => void;
};

export function AddressProfileDeletePanel({
  onCancel,
  onDeleted,
}: AddressProfileDeletePanelProps) {
  const [isWarningOpen, setIsWarningOpen] = useState(true);
  const deleteAddressProfile = useDeleteMyProfileAddress();
  const isDisabled = deleteAddressProfile.isPending;

  function closeWarning() {
    setIsWarningOpen(false);
    onCancel?.();
  }

  async function handleDeleteAddressProfile() {
    const result = await deleteAddressProfile.mutateAsync();

    if (result.ok) {
      setIsWarningOpen(false);
      onDeleted?.();
    }
  }

  return (
    <WarningModal
      confirmLabel="Delete address"
      description="This removes the address lines, city, state, postal code, and country from your profile."
      isBusy={isDisabled}
      isOpen={isWarningOpen}
      onClose={closeWarning}
      onConfirm={handleDeleteAddressProfile}
      title="Delete address profile?"
    >
      {deleteAddressProfile.data && !deleteAddressProfile.data.ok ? (
        <div className="auth-error" role="alert">
          {deleteAddressProfile.data.message}
        </div>
      ) : null}

      {deleteAddressProfile.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Address profile deleted.</strong>
          <p>The address section should refresh automatically.</p>
        </div>
      ) : null}

      {deleteAddressProfile.isError ? (
        <div className="auth-error" role="alert">
          Address profile delete failed before the server returned a response.
        </div>
      ) : null}
    </WarningModal>
  );
}
