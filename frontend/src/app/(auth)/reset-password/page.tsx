"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { authApi } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [email, setEmail] = useState<string | null>(null);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { setTokenValid(false); return; }
    authApi.checkResetToken(token)
      .then(r => { setEmail(r.data.email); setTokenValid(true); })
      .catch(() => setTokenValid(false));
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Passwort muss mindestens 8 Zeichen lang sein"); return; }
    if (password !== confirm) { setError("Passwörter stimmen nicht überein"); return; }
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      router.push("/login?reset=1");
    } catch {
      setError("Link ungültig oder abgelaufen. Bitte fordere einen neuen Reset-Link an.");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground";

  return (
    <div className="max-w-md w-full space-y-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-ctp-blue">VERA</h1>
        <p className="mt-2 text-muted-foreground">Neues Passwort vergeben</p>
      </div>

      <div className="bg-card rounded-xl shadow-md border border-border p-8">
        {tokenValid === null && (
          <p className="text-center text-muted-foreground">Link wird geprüft...</p>
        )}
        {tokenValid === false && (
          <div className="text-center space-y-4">
            <p className="text-ctp-red font-medium">Link ungültig oder abgelaufen</p>
            <a href="/auth/forgot-password" className="text-ctp-blue hover:underline text-sm block">
              Neuen Reset-Link anfordern
            </a>
          </div>
        )}
        {tokenValid === true && (
          <>
            <h2 className="text-xl font-semibold mb-2 text-foreground">Neues Passwort</h2>
            {email && (
              <p className="text-sm text-muted-foreground mb-6">
                Konto: <span className="font-medium text-foreground">{email}</span>
              </p>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground">Neues Passwort</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className={inputCls}
                  placeholder="Mindestens 8 Zeichen"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground">Passwort wiederholen</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={e => setConfirm(e.target.value)}
                  required
                  className={inputCls}
                  placeholder="••••••••"
                />
              </div>
              {error && <p className="text-ctp-red text-sm">{error}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-primary text-primary-foreground rounded-lg py-2.5 font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                {loading ? "Speichern..." : "Passwort speichern"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="fixed top-4 right-4 rounded-lg overflow-hidden" style={{ backgroundColor: "rgb(var(--card))", border: "1px solid rgb(var(--border))" }}>
        <ThemeToggle />
      </div>
      <Suspense fallback={<div className="text-muted-foreground">Laden...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
