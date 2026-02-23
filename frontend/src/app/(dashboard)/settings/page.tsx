"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { Settings, KeyRound, User, ShieldCheck, Eye, EyeOff } from "lucide-react";

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrator",
  manager: "Verwalter",
  employee: "Mitarbeiter",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "--ctp-red",
  manager: "--ctp-peach",
  employee: "--ctp-blue",
};

function PasswordField({
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <label className="text-xs text-muted-foreground block mb-1">{label}</label>
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          placeholder={placeholder || "••••••••"}
          className="w-full border border-border rounded-lg px-3 py-2 pr-10 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          tabIndex={-1}
        >
          {visible ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuthStore();
  const role = user?.role ?? "employee";
  const color = ROLE_COLORS[role] ?? "--ctp-blue";

  // Password change state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  const changePwMutation = useMutation({
    mutationFn: () => authApi.changePassword(currentPw, newPw),
    onSuccess: () => {
      toast.success("Passwort erfolgreich geändert");
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Fehler beim Ändern des Passworts");
    },
  });

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) {
      toast.error("Neue Passwörter stimmen nicht überein");
      return;
    }
    if (newPw.length < 8) {
      toast.error("Neues Passwort muss mindestens 8 Zeichen lang sein");
      return;
    }
    changePwMutation.mutate();
  };

  return (
    <div className="space-y-6 max-w-xl">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Einstellungen</h1>
        <p className="text-sm text-muted-foreground mt-0.5">Konto & Erscheinungsbild</p>
      </div>

      {/* Account info */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center gap-2">
          <User size={18} style={{ color: `rgb(var(${color}))` }} />
          <h2 className="font-semibold text-foreground">Mein Konto</h2>
        </div>
        <div className="flex items-center gap-4">
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold shrink-0"
            style={{
              backgroundColor: `rgb(var(${color}) / 0.15)`,
              color: `rgb(var(${color}))`,
            }}
          >
            {user?.email?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-foreground truncate">{user?.email}</p>
            <span
              className="inline-block text-xs px-2 py-0.5 rounded-full font-medium mt-0.5"
              style={{
                backgroundColor: `rgb(var(${color}) / 0.12)`,
                color: `rgb(var(${color}))`,
              }}
            >
              {ROLE_LABELS[role] ?? role}
            </span>
          </div>
        </div>
      </div>

      {/* Theme */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-3">
        <div className="flex items-center gap-2">
          <Settings size={18} style={{ color: "rgb(var(--ctp-mauve))" }} />
          <h2 className="font-semibold text-foreground">Erscheinungsbild</h2>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-foreground">Farbschema</p>
            <p className="text-xs text-muted-foreground">Wähle zwischen hellem und dunklem Design</p>
          </div>
          <div
            className="rounded-lg border border-border overflow-hidden"
            style={{ backgroundColor: "rgb(var(--sidebar-bg))", color: "rgb(var(--sidebar-fg))" }}
          >
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Password change */}
      <div className="bg-card rounded-xl border border-border p-5 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound size={18} style={{ color: "rgb(var(--ctp-green))" }} />
          <h2 className="font-semibold text-foreground">Passwort ändern</h2>
        </div>
        <form onSubmit={handlePasswordSubmit} className="space-y-3">
          <PasswordField
            label="Aktuelles Passwort"
            value={currentPw}
            onChange={setCurrentPw}
            required
          />
          <PasswordField
            label="Neues Passwort"
            value={newPw}
            onChange={setNewPw}
            placeholder="Mind. 8 Zeichen"
            required
          />
          <PasswordField
            label="Neues Passwort bestätigen"
            value={confirmPw}
            onChange={setConfirmPw}
            required
          />
          {newPw && confirmPw && newPw !== confirmPw && (
            <p className="text-xs" style={{ color: "rgb(var(--ctp-red))" }}>
              Passwörter stimmen nicht überein
            </p>
          )}
          <div className="pt-1">
            <button
              type="submit"
              disabled={changePwMutation.isPending || !currentPw || !newPw || !confirmPw}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-green))" }}
            >
              {changePwMutation.isPending ? (
                "Wird gespeichert…"
              ) : (
                <>
                  <ShieldCheck size={15} />
                  Passwort ändern
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
