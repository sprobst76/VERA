import { redirect } from "next/navigation";

// Selbst-Registrierung ist deaktiviert – alle Zugriffe zur Login-Seite umleiten
export default function RegisterPage() {
  redirect("/login");
}
