"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

function AcceptInviteForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";
  const fetchMe = useAuthStore(s => s.fetchMe);

  const [email, setEmail] = useState<string | null>(null);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) { setTokenValid(false); return; }
    authApi.checkInviteToken(token)
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
      const res = await authApi.acceptInvite(token, password);
      const { access_token, refresh_token } = res.data;
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      await fetchMe();
      router.push("/");
    } catch {
      setError("Einladungslink ungültig oder abgelaufen.");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground";

  return (
    <div className="max-w-md w-full space-y-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-ctp-blue">VERA</h1>
        <p className="mt-2 text-muted-foreground">Willkommen! Passwort vergeben</p>
      </div>

      <div className="bg-card rounded-xl shadow-md border border-border p-8">
        {tokenValid === null && (
          <p className="text-center text-muted-foreground">Einladung wird geprüft...</p>
        )}
        {tokenValid === false && (
          <div className="text-center space-y-4">
            <p className="text-ctp-red font-medium">Einladungslink ungültig oder abgelaufen</p>
            <p className="text-sm text-muted-foreground">
              Bitte wende dich an deinen Administrator für einen neuen Einladungslink.
            </p>
            <a href="/login" className="text-ctp-blue hover:underline text-sm block">
              Zur Anmeldung
            </a>
          </div>
        )}
        {tokenValid === true && (
          <>
            <h2 className="text-xl font-semibold mb-2 text-foreground">Konto aktivieren</h2>
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
                {loading ? "Aktivieren..." : "Konto aktivieren & anmelden"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="fixed top-4 right-4 rounded-lg overflow-hidden" style={{ backgroundColor: "rgb(var(--card))", border: "1px solid rgb(var(--border))" }}>
        <ThemeToggle />
      </div>
      <Suspense fallback={<div className="text-muted-foreground">Laden...</div>}>
        <AcceptInviteForm />
      </Suspense>
    </div>
  );
}
