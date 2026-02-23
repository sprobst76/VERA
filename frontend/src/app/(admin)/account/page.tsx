"use client";

import { useState } from "react";
import { useSuperAdminStore, getSuperAdminApi } from "@/store/superadmin";
import toast from "react-hot-toast";
import QRCode from "react-qr-code";
import { Shield, ShieldCheck, ShieldOff, KeyRound, Copy, Check } from "lucide-react";

function useApi() {
  return getSuperAdminApi();
}

type SetupStep = "idle" | "qr" | "confirm" | "done";

export default function AccountPage() {
  const api = useApi();
  const email = useSuperAdminStore((s) => s.email);

  // 2FA Setup State
  const [setupStep, setSetupStep] = useState<SetupStep>("idle");
  const [totpUri, setTotpUri] = useState("");
  const [secret, setSecret] = useState("");
  const [confirmCode, setConfirmCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);

  // 2FA Disable State
  const [showDisable, setShowDisable] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");

  // Initiiert Setup – holt Secret + URI vom Backend
  const startSetup = async () => {
    setLoading(true);
    try {
      const res = await api.post("/2fa/setup");
      setSecret(res.data.secret);
      setTotpUri(res.data.totp_uri);
      setSetupStep("qr");
    } catch {
      toast.error("Setup fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  // Bestätigt den TOTP-Code
  const confirmSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/2fa/confirm", { totp_code: confirmCode });
      toast.success("2FA erfolgreich aktiviert!");
      setSetupStep("done");
      setConfirmCode("");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Ungültiger Code");
    } finally {
      setLoading(false);
    }
  };

  // Deaktiviert 2FA
  const disable2fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.delete("/2fa", { data: { password: disablePassword, totp_code: disableCode } });
      toast.success("2FA deaktiviert");
      setShowDisable(false);
      setDisablePassword("");
      setDisableCode("");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Fehler beim Deaktivieren");
    } finally {
      setLoading(false);
    }
  };

  const copySecret = () => {
    navigator.clipboard.writeText(secret);
    setCopiedSecret(true);
    setTimeout(() => setCopiedSecret(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Account</h1>
        <p className="text-muted-foreground text-sm mt-0.5">{email}</p>
      </div>

      {/* 2FA-Sektion */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Shield size={18} style={{ color: "rgb(var(--ctp-red))" }} />
          <h2 className="font-semibold text-foreground">Zwei-Faktor-Authentifizierung</h2>
        </div>

        {setupStep === "idle" && !showDisable && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Schütze deinen Account mit einem Authenticator (Google Authenticator, Authy, etc.).
              Nach der Aktivierung wird beim Login nach einem 6-stelligen Code gefragt.
            </p>
            <div className="flex gap-3">
              <button onClick={startSetup} disabled={loading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
                style={{ backgroundColor: "rgb(var(--ctp-green))" }}>
                <ShieldCheck size={15} />
                {loading ? "Lade…" : "2FA einrichten"}
              </button>
              <button onClick={() => setShowDisable(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:text-foreground transition-colors">
                <ShieldOff size={15} />
                2FA deaktivieren
              </button>
            </div>
          </div>
        )}

        {/* Schritt 1: QR-Code scannen */}
        {setupStep === "qr" && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Scanne den QR-Code mit deiner Authenticator-App.
            </p>
            <div className="flex justify-center p-4 bg-white rounded-lg border border-border">
              <QRCode value={totpUri} size={180} />
            </div>

            <div>
              <p className="text-xs text-muted-foreground mb-1">
                Kein QR-Scanner? Gib den Code manuell ein:
              </p>
              <div className="flex gap-2">
                <code className="flex-1 text-xs font-mono bg-muted rounded-lg px-3 py-2 break-all text-muted-foreground select-all">
                  {secret}
                </code>
                <button onClick={copySecret}
                  className="shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-colors"
                  style={copiedSecret
                    ? { color: "rgb(var(--ctp-green))", backgroundColor: "rgb(var(--ctp-green) / 0.12)" }
                    : { color: "rgb(var(--ctp-blue))", backgroundColor: "rgb(var(--ctp-blue) / 0.12)" }}>
                  {copiedSecret ? <Check size={13} /> : <Copy size={13} />}
                </button>
              </div>
            </div>

            <button onClick={() => setSetupStep("confirm")}
              className="w-full py-2.5 rounded-lg text-sm font-medium text-white transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
              Code gescannt → weiter
            </button>
          </div>
        )}

        {/* Schritt 2: Code bestätigen */}
        {setupStep === "confirm" && (
          <form onSubmit={confirmSetup} className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Gib den 6-stelligen Code aus der App ein, um die Einrichtung zu bestätigen.
            </p>
            <div className="flex items-center gap-2">
              <KeyRound size={16} className="text-muted-foreground shrink-0" />
              <input
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                value={confirmCode}
                onChange={(e) => setConfirmCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                autoFocus
                required
                placeholder="000000"
                className="flex-1 border border-border rounded-lg px-3 py-2.5 bg-background text-foreground text-center text-xl font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => setSetupStep("qr")}
                className="flex-1 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-accent transition-colors">
                ← Zurück
              </button>
              <button type="submit" disabled={loading || confirmCode.length !== 6}
                className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
                style={{ backgroundColor: "rgb(var(--ctp-green))" }}>
                {loading ? "Prüfen…" : "Aktivieren"}
              </button>
            </div>
          </form>
        )}

        {/* Erfolgreich aktiviert */}
        {setupStep === "done" && (
          <div className="flex items-center gap-3 p-3 rounded-lg"
            style={{ backgroundColor: "rgb(var(--ctp-green) / 0.12)" }}>
            <ShieldCheck size={18} style={{ color: "rgb(var(--ctp-green))" }} />
            <div>
              <p className="text-sm font-medium" style={{ color: "rgb(var(--ctp-green))" }}>
                2FA ist jetzt aktiv
              </p>
              <p className="text-xs text-muted-foreground">
                Ab dem nächsten Login wird der Authenticator-Code abgefragt.
              </p>
            </div>
          </div>
        )}

        {/* 2FA deaktivieren */}
        {showDisable && (
          <form onSubmit={disable2fa} className="space-y-3 border-t border-border pt-4">
            <p className="text-sm font-medium text-foreground">2FA deaktivieren</p>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Passwort</label>
              <input type="password" value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)} required
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Aktueller Authenticator-Code</label>
              <input type="text" inputMode="numeric" maxLength={6}
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                required placeholder="000000"
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-center font-mono text-lg tracking-widest focus:outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => setShowDisable(false)}
                className="flex-1 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-accent transition-colors">
                Abbrechen
              </button>
              <button type="submit" disabled={loading}
                className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
                style={{ backgroundColor: "rgb(var(--ctp-red))" }}>
                {loading ? "Deaktivieren…" : "Deaktivieren"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
