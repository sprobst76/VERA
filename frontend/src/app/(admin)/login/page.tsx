"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSuperAdminStore } from "@/store/superadmin";
import toast from "react-hot-toast";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Shield, KeyRound } from "lucide-react";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://192.168.0.144:31367";

type Step = "credentials" | "totp";

export default function SuperAdminLoginPage() {
  const router = useRouter();
  const { login, isLoading } = useSuperAdminStore();

  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challengeToken, setChallengeToken] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [verifying, setVerifying] = useState(false);

  // Schritt 1: E-Mail + Passwort
  const onSubmitCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      // login() im Store setzt isAuthenticated – aber nur wenn kein 2FA nötig
      router.push("/admin/tenants");
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.requires_2fa && data?.challenge_token) {
        // 2FA erforderlich → zum zweiten Schritt
        setChallengeToken(data.challenge_token);
        setStep("totp");
      } else {
        toast.error("Ungültige Anmeldedaten");
      }
    }
  };

  // Schritt 2: TOTP-Code
  const onSubmitTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    try {
      const res = await axios.post(`${API_URL}/api/v1/superadmin/login/verify-2fa`, {
        challenge_token: challengeToken,
        totp_code: totpCode,
      });
      const { access_token } = res.data;
      // Token manuell in den Store schreiben
      useSuperAdminStore.setState({ token: access_token, email, isAuthenticated: true });
      router.push("/admin/tenants");
    } catch {
      toast.error("Ungültiger Code – bitte erneut versuchen");
      setTotpCode("");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="fixed top-4 right-4 rounded-lg overflow-hidden"
        style={{ backgroundColor: "rgb(var(--card))", border: "1px solid rgb(var(--border))" }}>
        <ThemeToggle />
      </div>

      <div className="max-w-sm w-full space-y-8">
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Shield size={32} style={{ color: "rgb(var(--ctp-red))" }} />
            <h1 className="text-3xl font-bold text-foreground">VERA</h1>
          </div>
          <p className="text-muted-foreground text-sm">System-Administration</p>
        </div>

        <div className="bg-card rounded-xl shadow-md border border-border p-8">
          {step === "credentials" ? (
            <>
              <h2 className="text-lg font-semibold mb-5 text-foreground">SuperAdmin Login</h2>
              <form onSubmit={onSubmitCredentials} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1 text-foreground">E-Mail</label>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                    className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="admin@vera.de" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-foreground">Passwort</label>
                  <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
                    className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="••••••••" />
                </div>
                <button type="submit" disabled={isLoading}
                  className="w-full rounded-lg py-2.5 font-medium transition-colors disabled:opacity-50 text-white"
                  style={{ backgroundColor: "rgb(var(--ctp-red))" }}>
                  {isLoading ? "Anmelden..." : "Anmelden"}
                </button>
              </form>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-5">
                <KeyRound size={18} style={{ color: "rgb(var(--ctp-peach))" }} />
                <h2 className="text-lg font-semibold text-foreground">Authenticator-Code</h2>
              </div>
              <p className="text-sm text-muted-foreground mb-4">
                Gib den 6-stelligen Code aus deiner Authenticator-App ein.
              </p>
              <form onSubmit={onSubmitTotp} className="space-y-4">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{6}"
                  maxLength={6}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  autoFocus
                  required
                  placeholder="000000"
                  className="w-full border border-border rounded-lg px-3 py-3 bg-background text-foreground text-center text-2xl font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <button type="submit" disabled={verifying || totpCode.length !== 6}
                  className="w-full rounded-lg py-2.5 font-medium transition-colors disabled:opacity-50 text-white"
                  style={{ backgroundColor: "rgb(var(--ctp-red))" }}>
                  {verifying ? "Prüfen…" : "Bestätigen"}
                </button>
                <button type="button" onClick={() => { setStep("credentials"); setTotpCode(""); }}
                  className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors">
                  ← Zurück zur Anmeldung
                </button>
              </form>
            </>
          )}
        </div>

        <p className="text-center text-xs text-muted-foreground">
          Regulärer Login:{" "}
          <a href="/login" className="underline hover:text-foreground">zur App</a>
        </p>
      </div>
    </div>
  );
}
