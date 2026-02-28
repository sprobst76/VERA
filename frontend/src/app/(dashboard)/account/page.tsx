"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { employeesApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { UserCircle, Pencil, Check, X, ExternalLink } from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";

const CONTRACT_LABELS: Record<string, string> = {
  minijob: "Minijob",
  part_time: "Teilzeit",
  full_time: "Vollzeit",
};

export default function AccountPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const isEmployee = user?.role === "employee";

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ["employees", "me"],
    queryFn: () => employeesApi.me().then(r => r.data),
    enabled: isEmployee,
  });

  const [editing, setEditing] = useState(false);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  const mutation = useMutation({
    mutationFn: (data: { phone: string | null; email: string | null }) =>
      employeesApi.updateMe(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees", "me"] });
      toast.success("Profil aktualisiert");
      setEditing(false);
    },
    onError: () => toast.error("Fehler beim Speichern"),
  });

  const startEdit = () => {
    setPhone(profile?.phone ?? "");
    setEmail(profile?.email ?? "");
    setEditing(true);
  };

  const save = () => {
    mutation.mutate({
      phone: phone.trim() || null,
      email: email.trim() || null,
    });
  };

  // ── Admin/Manager: kein eigenes Employee-Profil ────────────────────────────
  if (!isEmployee) {
    return (
      <div className="max-w-lg">
        <h1 className="text-2xl font-bold mb-6">Mein Profil</h1>
        <div className="bg-card border border-border rounded-xl p-6 text-sm text-muted-foreground space-y-3">
          <p>Als Admin oder Manager wird dein Profil über die Mitarbeiterverwaltung gepflegt.</p>
          <Link
            href="/employees"
            className="inline-flex items-center gap-2 text-primary hover:underline font-medium"
          >
            Zur Mitarbeiterverwaltung <ExternalLink size={14} />
          </Link>
        </div>
      </div>
    );
  }

  // ── Loading / Error ────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
        Wird geladen…
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="max-w-lg">
        <h1 className="text-2xl font-bold mb-6">Mein Profil</h1>
        <div className="bg-card border border-border rounded-xl p-6 text-sm text-muted-foreground">
          Kein Mitarbeiterprofil mit diesem Account verknüpft. Bitte Admin kontaktieren.
        </div>
      </div>
    );
  }

  // ── Employee-Ansicht ───────────────────────────────────────────────────────
  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-2xl font-bold">Mein Profil</h1>

      {/* ── Profil-Info (read-only) ── */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center gap-3">
          <UserCircle size={20} className="text-muted-foreground" />
          <span className="font-semibold text-sm">Profil</span>
        </div>
        <dl className="divide-y divide-border text-sm">
          <Row label="Name" value={`${profile.first_name} ${profile.last_name}`} />
          <Row label="Vertragsart" value={CONTRACT_LABELS[profile.contract_type] ?? profile.contract_type} />
          <Row label="Stundenlohn" value={`${Number(profile.hourly_rate).toFixed(2)} €`} />
          {profile.monthly_hours_limit != null && (
            <Row label="Stundenlimit / Monat" value={`${profile.monthly_hours_limit} h`} />
          )}
          {profile.weekly_hours != null && (
            <Row label="Wochenstunden" value={`${profile.weekly_hours} h`} />
          )}
          <Row label="Urlaubstage" value={`${profile.vacation_days} Tage / Jahr`} />
          {profile.qualifications?.length > 0 && (
            <Row
              label="Qualifikationen"
              value={
                <div className="flex flex-wrap gap-1">
                  {profile.qualifications.map((q: string) => (
                    <span key={q} className="text-xs px-2 py-0.5 rounded-full bg-accent text-accent-foreground">
                      {q}
                    </span>
                  ))}
                </div>
              }
            />
          )}
        </dl>
      </div>

      {/* ── Kontakt (editierbar) ── */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <span className="font-semibold text-sm">Kontakt</span>
          {!editing && (
            <button
              onClick={startEdit}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Pencil size={13} /> Bearbeiten
            </button>
          )}
        </div>

        {editing ? (
          <div className="p-5 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Telefon</label>
              <input
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                placeholder="z. B. +49 151 12345678"
                className="w-full text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">E-Mail</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="z. B. anna@beispiel.de"
                className="w-full text-sm border border-border rounded-lg px-3 py-2 bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={save}
                disabled={mutation.isPending}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                <Check size={14} /> Speichern
              </button>
              <button
                onClick={() => setEditing(false)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-card border border-border hover:bg-accent transition-colors"
              >
                <X size={14} /> Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <dl className="divide-y divide-border text-sm">
            <Row label="Telefon" value={profile.phone ?? <span className="text-muted-foreground italic">nicht hinterlegt</span>} />
            <Row label="E-Mail" value={profile.email ?? <span className="text-muted-foreground italic">nicht hinterlegt</span>} />
          </dl>
        )}
      </div>
    </div>
  );
}

// ── Helper ─────────────────────────────────────────────────────────────────

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="px-5 py-3 flex items-start justify-between gap-4">
      <dt className="text-muted-foreground shrink-0 w-40">{label}</dt>
      <dd className="text-foreground text-right">{value}</dd>
    </div>
  );
}
