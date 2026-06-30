import { AuthCard } from "@/auth/components/AuthCard";
import { RegisterForm } from "@/auth/components/RegisterForm";

export function RegisterPage() {
  return (
    <AuthCard>
      <RegisterForm />
    </AuthCard>
  );
}