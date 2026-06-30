import { AuthCard } from "@/auth/components/AuthCard";
import { LoginForm } from "@/auth/components/LoginForm";

export function LoginPage() {
  return (
    <AuthCard>
      <LoginForm />
    </AuthCard>
  );
}