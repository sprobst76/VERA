"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSuperAdminApi, useSuperAdminStore } from "@/store/superadmin";
import toast from "react-hot-toast";
import { Plus, Shield, X, ToggleLeft, ToggleRight } from "lucide-react";
import { format, parseISO } from "date-fns";
import { de } from "date-fns/locale";

interface SuperAdmin {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

function useApi() {
  return getSuperAdminApi();
}

function CreateAdminModal({ onClose }: { onClose: () => void }) {
  const api = useApi();
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/admins", { email, password });
      toast.success(`SuperAdmin „${email}" erstellt`);
      qc.invalidateQueries({ queryKey: ["sa-admins"] });
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
          <h2 className="font-semibold text-foreground">Neuer SuperAdmin</h2>
          <button onClick={onClose}><X size={18} className="text-muted-foreground" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground block mb-1">E-Mail</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="admin@vera.de" />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground block mb-1">
              Passwort <span className="text-muted-foreground font-normal">(min. 8 Zeichen)</span>
            </label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8}
              className="w-full border border-border rounded-lg px-3 py-2 bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="••••••••" />
          </div>
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-accent transition-colors">
              Abbrechen
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors"
              style={{ backgroundColor: "rgb(var(--ctp-red))" }}>
              {loading ? "Erstellen…" : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminsPage() {
  const api = useApi();
  const qc = useQueryClient();
  const currentEmail = useSuperAdminStore((s) => s.email);
  const [createOpen, setCreateOpen] = useState(false);

  const { data: admins = [], isLoading } = useQuery<SuperAdmin[]>({
    queryKey: ["sa-admins"],
    queryFn: () => api.get("/admins").then((r) => r.data),
  });

  const toggleActive = async (admin: SuperAdmin) => {
    if (admin.email === currentEmail) {
      toast.error("Eigenen Account nicht deaktivierbar");
      return;
    }
    try {
      await api.patch(`/admins/${admin.id}`, { is_active: !admin.is_active });
      toast.success(admin.is_active ? "Deaktiviert" : "Aktiviert");
      qc.invalidateQueries({ queryKey: ["sa-admins"] });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Fehler");
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">SuperAdmins</h1>
          <p className="text-muted-foreground text-sm mt-0.5">{admins.length} Administratoren</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
          style={{ backgroundColor: "rgb(var(--ctp-red))" }}
        >
          <Plus size={16} />
          Neuer Admin
        </button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground text-sm">Lade…</p>
      ) : (
        <div className="space-y-2">
          {admins.map((admin) => (
            <div key={admin.id}
              className={`bg-card rounded-xl border border-border p-4 flex items-center gap-4 transition-opacity ${!admin.is_active ? "opacity-60" : ""}`}>
              <Shield size={18} style={{ color: "rgb(var(--ctp-red))", flexShrink: 0 }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-foreground text-sm">{admin.email}</span>
                  {admin.email === currentEmail && (
                    <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-accent text-muted-foreground">Ich</span>
                  )}
                  {!admin.is_active && (
                    <span className="text-xs px-1.5 py-0.5 rounded font-medium"
                      style={{ color: "rgb(var(--ctp-red))", backgroundColor: "rgb(var(--ctp-red) / 0.12)" }}>
                      Deaktiviert
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Seit {format(parseISO(admin.created_at), "dd.MM.yyyy", { locale: de })}
                </p>
              </div>
              {admin.email !== currentEmail && (
                <button
                  onClick={() => toggleActive(admin)}
                  title={admin.is_active ? "Deaktivieren" : "Aktivieren"}
                  className="shrink-0 p-1.5 rounded hover:bg-accent transition-colors"
                >
                  {admin.is_active
                    ? <ToggleRight size={20} style={{ color: "rgb(var(--ctp-green))" }} />
                    : <ToggleLeft size={20} className="text-muted-foreground" />}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {createOpen && <CreateAdminModal onClose={() => setCreateOpen(false)} />}
    </div>
  );
}
