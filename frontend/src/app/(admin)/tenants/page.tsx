"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSuperAdminStore, getSuperAdminApi } from "@/store/superadmin";
import toast from "react-hot-toast";
import {
  Building2, Plus, Users, UserCheck, CheckCircle2,
  XCircle, Pencil, ChevronDown, ChevronUp, X,
} from "lucide-react";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

// ── API helpers ──────────────────────────────────────────────────────────────

function useApi() {
  const token = useSuperAdminStore((s) => s.token);
  return getSuperAdminApi();
}

// ── Typen ────────────────────────────────────────────────────────────────────

interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  state: string;
  is_active: boolean;
  created_at: string;
  user_count: number;
  employee_count: number;
}

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

const STATE_OPTIONS = [
  "BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV",
  "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH",
];

// ── Modal: Tenant erstellen ───────────────────────────────────────────────────

function CreateTenantModal({ onClose }: { onClose: () => void }) {
  const api = useApi();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", slug: "", state: "BW", plan: "free",
    admin_email: "", admin_password: "",
  });
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/tenants", form);
      toast.success(`Tenant „${form.name}" erstellt`);
      qc.invalidateQueries({ queryKey: ["sa-tenants"] });
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Fehler beim Erstellen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-card rounded-xl border border-border shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-foreground">Neuen Tenant anlegen</h2>
          <button onClick={onClose}><X size={18} className="text-muted-foreground" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <fieldset className="space-y-3">
            <legend className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Organisation</legend>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Name</label>
              <input value={form.name} onChange={(e) => set("name", e.target.value)} required
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Stefans Pflegedienst" />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Slug <span className="text-muted-foreground font-normal">(a-z, 0-9, -)</span></label>
              <input value={form.slug} onChange={(e) => set("slug", e.target.value.toLowerCase())} required
                pattern="[a-z0-9-]+"
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="stefan-pflegedienst" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-foreground block mb-1">Bundesland</label>
                <select value={form.state} onChange={(e) => set("state", e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                  {STATE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground block mb-1">Plan</label>
                <select value={form.plan} onChange={(e) => set("plan", e.target.value)}
                  className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                  {Object.entries(PLAN_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>
            </div>
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Erster Admin-Account</legend>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">E-Mail</label>
              <input type="email" value={form.admin_email} onChange={(e) => set("admin_email", e.target.value)} required
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="admin@example.de" />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Passwort <span className="text-muted-foreground font-normal">(min. 8 Zeichen)</span></label>
              <input type="password" value={form.admin_password} onChange={(e) => set("admin_password", e.target.value)} required minLength={8}
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="••••••••" />
            </div>
          </fieldset>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-accent transition-colors">
              Abbrechen
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
              {loading ? "Erstellen…" : "Tenant erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Modal: Tenant bearbeiten ──────────────────────────────────────────────────

function EditTenantModal({ tenant, onClose }: { tenant: Tenant; onClose: () => void }) {
  const api = useApi();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: tenant.name,
    plan: tenant.plan,
    state: tenant.state,
    is_active: tenant.is_active,
  });
  const [loading, setLoading] = useState(false);

  const set = (k: string, v: string | boolean) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.patch(`/tenants/${tenant.id}`, form);
      toast.success("Tenant aktualisiert");
      qc.invalidateQueries({ queryKey: ["sa-tenants"] });
      onClose();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Fehler");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-card rounded-xl border border-border shadow-xl w-full max-w-sm">
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-foreground">Tenant bearbeiten</h2>
          <button onClick={onClose}><X size={18} className="text-muted-foreground" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground block mb-1">Name</label>
            <input value={form.name} onChange={(e) => set("name", e.target.value)} required
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Bundesland</label>
              <select value={form.state} onChange={(e) => set("state", e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                {STATE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Plan</label>
              <select value={form.plan} onChange={(e) => set("plan", e.target.value)}
                className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
                {Object.entries(PLAN_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 rounded-lg border border-border">
            <input type="checkbox" id="is_active" checked={form.is_active}
              onChange={(e) => set("is_active", e.target.checked)}
              className="w-4 h-4 rounded" />
            <label htmlFor="is_active" className="text-sm text-foreground">
              Tenant aktiv
              <span className="block text-xs text-muted-foreground">
                Deaktivieren sperrt alle Benutzer dieses Tenants
              </span>
            </label>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-accent transition-colors">
              Abbrechen
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}>
              {loading ? "Speichern…" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Tenant-Zeile ─────────────────────────────────────────────────────────────

function TenantRow({ tenant }: { tenant: Tenant }) {
  const [editOpen, setEditOpen] = useState(false);

  return (
    <>
      <div className={`bg-card rounded-xl border p-4 transition-opacity ${tenant.is_active ? "border-border" : "border-border opacity-60"}`}>
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-foreground">{tenant.name}</h3>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={tenant.is_active
                  ? { color: "rgb(var(--ctp-green))", backgroundColor: "rgb(var(--ctp-green) / 0.12)" }
                  : { color: "rgb(var(--ctp-red))", backgroundColor: "rgb(var(--ctp-red) / 0.12)" }}>
                {tenant.is_active ? "Aktiv" : "Deaktiviert"}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-accent text-muted-foreground">
                {PLAN_LABELS[tenant.plan] ?? tenant.plan}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mt-0.5">
              <span className="font-mono text-xs">{tenant.slug}</span>
              {" · "}{tenant.state}
              {" · "}erstellt {format(parseISO(tenant.created_at), "dd.MM.yyyy", { locale: de })}
            </p>
          </div>
          <button
            onClick={() => setEditOpen(true)}
            className="shrink-0 p-2 rounded-lg hover:bg-accent transition-colors"
            title="Bearbeiten"
          >
            <Pencil size={15} className="text-muted-foreground" />
          </button>
        </div>

        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border">
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Users size={14} />
            <span>{tenant.user_count} Benutzer</span>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <UserCheck size={14} />
            <span>{tenant.employee_count} Mitarbeiter</span>
          </div>
        </div>
      </div>

      {editOpen && <EditTenantModal tenant={tenant} onClose={() => setEditOpen(false)} />}
    </>
  );
}

// ── Hauptseite ────────────────────────────────────────────────────────────────

export default function TenantsPage() {
  const api = useApi();
  const [createOpen, setCreateOpen] = useState(false);

  const { data: tenants = [], isLoading } = useQuery<Tenant[]>({
    queryKey: ["sa-tenants"],
    queryFn: () => api.get("/tenants").then((r) => r.data),
  });

  const active = tenants.filter((t) => t.is_active);
  const inactive = tenants.filter((t) => !t.is_active);

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Tenants</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {tenants.length} Tenant{tenants.length !== 1 ? "s" : ""} · {active.length} aktiv
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
          style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
        >
          <Plus size={16} />
          Neuer Tenant
        </button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Lade…</p>
      ) : tenants.length === 0 ? (
        <div className="bg-card rounded-xl border border-border p-8 text-center">
          <Building2 size={32} className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-muted-foreground">Noch keine Tenants vorhanden.</p>
          <button onClick={() => setCreateOpen(true)}
            className="mt-3 text-sm font-medium underline"
            style={{ color: "rgb(var(--ctp-blue))" }}>
            Ersten Tenant anlegen
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {active.map((t) => <TenantRow key={t.id} tenant={t} />)}
          {inactive.length > 0 && (
            <>
              <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide pt-2">Deaktiviert</p>
              {inactive.map((t) => <TenantRow key={t.id} tenant={t} />)}
            </>
          )}
        </div>
      )}

      {createOpen && <CreateTenantModal onClose={() => setCreateOpen(false)} />}
    </div>
  );
}
