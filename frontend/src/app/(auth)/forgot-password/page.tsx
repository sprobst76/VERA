"use client";

import { useState } from "react";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { authApi } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await authApi.forgotPassword(email);
      setSent(true);
    } catch {
      setError("Ein Fehler ist aufgetreten. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground";

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="fixed top-4 right-4 rounded-lg overflow-hidden" style={{ backgroundColor: "rgb(var(--card))", border: "1px solid rgb(var(--border))" }}>
        <ThemeToggle />
      </div>

      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-ctp-blue">VERA</h1>
          <p className="mt-2 text-muted-foreground">Passwort zurücksetzen</p>
        </div>

        <div className="bg-card rounded-xl shadow-md border border-border p-8">
          {sent ? (
            <div className="text-center space-y-4">
              <div className="text-4xl">✉️</div>
              <p className="text-foreground font-medium">E-Mail gesendet</p>
              <p className="text-sm text-muted-foreground">
                Falls ein Konto mit dieser E-Mail-Adresse existiert, wurde ein Reset-Link gesendet.
                Der Link ist 1 Stunde gültig.
              </p>
              <a href="/login" className="block mt-4 text-ctp-blue hover:underline text-sm">
                Zurück zur Anmeldung
              </a>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold mb-2 text-foreground">Passwort vergessen?</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Gib deine E-Mail-Adresse ein und wir schicken dir einen Reset-Link.
              </p>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1 text-foreground">E-Mail</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                    className={inputCls}
                    placeholder="deine@email.de"
                  />
                </div>

                {error && <p className="text-ctp-red text-sm">{error}</p>}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-primary text-primary-foreground rounded-lg py-2.5 font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {loading ? "Sende..." : "Reset-Link senden"}
                </button>
              </form>

              <p className="mt-4 text-center text-sm">
                <a href="/login" className="text-ctp-blue hover:underline">
                  Zurück zur Anmeldung
                </a>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
