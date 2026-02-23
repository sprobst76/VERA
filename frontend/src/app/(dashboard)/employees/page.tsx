"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Mail,
  Phone,
  Clock,
  Euro,
  Pencil,
  UserX,
  UserCheck,
  X,
  ChevronDown,
  ChevronUp,
  Link,
  Unlink,
  ShieldCheck,
  Eye,
  EyeOff,
} from "lucide-react";
import { employeesApi, usersApi } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import toast from "react-hot-toast";

/* ── Types ────────────────────────────────────────────────────────── */
interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  contract_type: string;
  hourly_rate: number;
  monthly_hours_limit: number | null;
  annual_salary_limit: number | null;
  vacation_days: number;
  qualifications: string[];
  is_active: boolean;
  user_id: string | null;
  created_at: string;
}

const CONTRACT_LABELS: Record<string, string> = {
  full_time: "Vollzeit",
  part_time: "Teilzeit",
  minijob: "Minijob",
};
const CONTRACT_COLORS: Record<string, string> = {
  full_time: "rgb(var(--ctp-blue))",
  part_time: "rgb(var(--ctp-green))",
  minijob: "rgb(var(--ctp-peach))",
};

const QUALIFICATION_SUGGESTIONS = [
  "Kassierer",
  "Lager",
  "Beratung",
  "Teamleitung",
  "Reinigung",
  "Küche",
  "Service",
  "Verkauf",
];

/* ── LinkAccountModal ────────────────────────────────────────────── */
interface UserEntry {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  has_employee: boolean;
}

interface LinkModalProps {
  employee: Employee;
  onClose: () => void;
  onSaved: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  manager: "Verwalter",
  employee: "Mitarbeiter",
};

function LinkAccountModal({ employee, onClose, onSaved }: LinkModalProps) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"link" | "create">(
    employee.user_id ? "link" : "link"
  );
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [newEmail, setNewEmail] = useState(employee.email ?? "");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("employee");
  const [showPw, setShowPw] = useState(false);

  const { data: users = [] } = useQuery<UserEntry[]>({
    queryKey: ["users"],
    queryFn: () => usersApi.list().then((r) => r.data),
  });

  // Users not yet linked to any employee (or linked to this employee)
  const availableUsers = users.filter(
    (u) => !u.has_employee || u.id === employee.user_id
  );

  const linkMutation = useMutation({
    mutationFn: (user_id: string | null) =>
      employeesApi.update(employee.id, { user_id: user_id ?? undefined } as Record<string, unknown>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success(
        selectedUserId
          ? "Login-Account verknüpft"
          : "Verknüpfung aufgehoben"
      );
      onSaved();
      onClose();
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Fehler beim Verknüpfen");
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      // Create user account
      const res = await usersApi.create({
        email: newEmail,
        password: newPassword,
        role: newRole,
      });
      const newUser = res.data;
      // Link to employee
      await employeesApi.update(employee.id, {
        user_id: newUser.id,
      } as Record<string, unknown>);
      return newUser;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success("Konto erstellt und verknüpft");
      onSaved();
      onClose();
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ?? "Fehler beim Erstellen");
    },
  });

  const currentLinkedUser = users.find((u) => u.id === employee.user_id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border">
          <div>
            <h2 className="font-semibold text-foreground">Login-Account verknüpfen</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {employee.first_name} {employee.last_name}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted text-muted-foreground"
          >
            <X size={18} />
          </button>
        </div>

        {/* Current link status */}
        {currentLinkedUser && (
          <div
            className="mx-5 mt-4 p-3 rounded-xl flex items-center gap-3"
            style={{ backgroundColor: "rgb(var(--ctp-green) / 0.10)" }}
          >
            <ShieldCheck size={16} style={{ color: "rgb(var(--ctp-green))" }} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-foreground truncate">
                {currentLinkedUser.email}
              </div>
              <div className="text-xs text-muted-foreground">
                {ROLE_LABELS[currentLinkedUser.role] ?? currentLinkedUser.role}
                {!currentLinkedUser.is_active && " · Inaktiv"}
              </div>
            </div>
            <button
              onClick={() => {
                if (confirm("Verknüpfung wirklich aufheben?")) {
                  linkMutation.mutate(null);
                }
              }}
              disabled={linkMutation.isPending}
              className="flex items-center gap-1 text-xs text-red-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-red-500/10"
            >
              <Unlink size={12} /> Aufheben
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 px-5 pt-4">
          {(["link", "create"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t
                  ? "text-white"
                  : "text-muted-foreground hover:bg-muted"
              }`}
              style={tab === t ? { backgroundColor: "rgb(var(--ctp-blue))" } : {}}
            >
              {t === "link" ? "Bestehendes Konto" : "Neues Konto erstellen"}
            </button>
          ))}
        </div>

        <div className="p-5 space-y-4">
          {tab === "link" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Login-Account auswählen
                </label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                >
                  <option value="">— Konto auswählen —</option>
                  {availableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.email} ({ROLE_LABELS[u.role] ?? u.role})
                      {u.id === employee.user_id ? " ✓ aktuell" : ""}
                      {!u.is_active ? " [inaktiv]" : ""}
                    </option>
                  ))}
                </select>
                {availableUsers.length === 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Alle Konten sind bereits verknüpft. Neues Konto erstellen?
                  </p>
                )}
              </div>
              <button
                onClick={() => linkMutation.mutate(selectedUserId || null)}
                disabled={!selectedUserId || linkMutation.isPending || selectedUserId === employee.user_id}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-40"
                style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
              >
                <Link size={14} className="inline mr-1.5" />
                {linkMutation.isPending ? "Verknüpfe…" : "Verknüpfen"}
              </button>
            </>
          )}

          {tab === "create" && (
            <>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  E-Mail *
                </label>
                <input
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  placeholder="anna@beispiel.de"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Passwort *
                </label>
                <div className="relative">
                  <input
                    type={showPw ? "text" : "password"}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-10 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    placeholder="Mindestens 8 Zeichen"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                  >
                    {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1.5">
                  Rolle
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["employee", "manager", "admin"] as const).map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => setNewRole(r)}
                      className="py-2 rounded-lg border text-xs font-medium transition-colors"
                      style={
                        newRole === r
                          ? {
                              borderColor: "rgb(var(--ctp-blue))",
                              color: "rgb(var(--ctp-blue))",
                              backgroundColor: "rgb(var(--ctp-blue) / 0.10)",
                            }
                          : { color: "rgb(var(--ctp-subtext0))" }
                      }
                    >
                      {ROLE_LABELS[r]}
                    </button>
                  ))}
                </div>
              </div>
              <button
                onClick={() => createMutation.mutate()}
                disabled={
                  !newEmail ||
                  !newPassword ||
                  newPassword.length < 8 ||
                  createMutation.isPending
                }
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-40"
                style={{ backgroundColor: "rgb(var(--ctp-green))" }}
              >
                {createMutation.isPending ? "Erstelle Konto…" : "Konto erstellen & verknüpfen"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── EmployeeModal ────────────────────────────────────────────────── */
interface ModalProps {
  employee?: Employee;
  onClose: () => void;
  onSaved: () => void;
}

function EmployeeModal({ employee, onClose, onSaved }: ModalProps) {
  const isEdit = !!employee;

  const [form, setForm] = useState({
    first_name: employee?.first_name ?? "",
    last_name: employee?.last_name ?? "",
    email: employee?.email ?? "",
    phone: employee?.phone ?? "",
    contract_type: employee?.contract_type ?? "minijob",
    hourly_rate: employee?.hourly_rate?.toString() ?? "",
    monthly_hours_limit: employee?.monthly_hours_limit?.toString() ?? "",
    annual_salary_limit: employee?.annual_salary_limit?.toString() ?? "6672",
    vacation_days: employee?.vacation_days?.toString() ?? "30",
  });
  const [qualifications, setQualifications] = useState<string[]>(
    employee?.qualifications ?? []
  );
  const [qualInput, setQualInput] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  function set(field: string, value: string) {
    setForm((f) => {
      const next = { ...f, [field]: value };
      // Auto-fill limits for Minijob
      if (field === "contract_type" && value === "minijob") {
        next.annual_salary_limit = "6672";
        if (!next.monthly_hours_limit) next.monthly_hours_limit = "43";
      }
      return next;
    });
  }

  function addQual(q: string) {
    const trimmed = q.trim();
    if (trimmed && !qualifications.includes(trimmed)) {
      setQualifications((prev) => [...prev, trimmed]);
    }
    setQualInput("");
  }

  function removeQual(q: string) {
    setQualifications((prev) => prev.filter((x) => x !== q));
  }

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      isEdit
        ? employeesApi.update(employee!.id, data)
        : employeesApi.create(data),
    onSuccess: () => {
      toast.success(isEdit ? "Mitarbeiter aktualisiert" : "Mitarbeiter angelegt");
      onSaved();
      onClose();
    },
    onError: (e: unknown) => {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail;
      toast.error(msg ?? "Fehler beim Speichern");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Record<string, unknown> = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      contract_type: form.contract_type,
      hourly_rate: parseFloat(form.hourly_rate),
      monthly_hours_limit: form.monthly_hours_limit
        ? parseFloat(form.monthly_hours_limit)
        : null,
      annual_salary_limit: form.annual_salary_limit
        ? parseFloat(form.annual_salary_limit)
        : null,
      vacation_days: parseInt(form.vacation_days),
      qualifications,
    };
    mutation.mutate(payload);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-card rounded-2xl border border-border w-full max-w-lg max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-semibold text-foreground text-lg">
            {isEdit ? "Mitarbeiter bearbeiten" : "Neuer Mitarbeiter"}
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted text-muted-foreground"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-5">
          {/* Name */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Vorname *
              </label>
              <input
                required
                value={form.first_name}
                onChange={(e) => set("first_name", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="Anna"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Nachname *
              </label>
              <input
                required
                value={form.last_name}
                onChange={(e) => set("last_name", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="Müller"
              />
            </div>
          </div>

          {/* Kontakt */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                E-Mail
              </label>
              <input
                type="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="anna@beispiel.de"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Telefon
              </label>
              <input
                value={form.phone}
                onChange={(e) => set("phone", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="+49 170 1234567"
              />
            </div>
          </div>

          {/* Vertragstyp */}
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-2">
              Vertragstyp *
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(["minijob", "part_time", "full_time"] as const).map((ct) => (
                <button
                  key={ct}
                  type="button"
                  onClick={() => set("contract_type", ct)}
                  className="py-2 px-3 rounded-lg border text-sm font-medium transition-all"
                  style={
                    form.contract_type === ct
                      ? {
                          borderColor: CONTRACT_COLORS[ct],
                          backgroundColor: CONTRACT_COLORS[ct] + " / 0.12)",
                          color: CONTRACT_COLORS[ct],
                          // inline style workaround:
                        }
                      : {}
                  }
                  data-selected={form.contract_type === ct}
                >
                  <span
                    style={
                      form.contract_type === ct
                        ? { color: CONTRACT_COLORS[ct] }
                        : { color: "rgb(var(--ctp-subtext0))" }
                    }
                  >
                    {CONTRACT_LABELS[ct]}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Vergütung */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Stundenlohn (€) *
              </label>
              <input
                required
                type="number"
                min="0"
                step="0.01"
                value={form.hourly_rate}
                onChange={(e) => set("hourly_rate", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="12.41"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">
                Std.-Limit / Monat
              </label>
              <input
                type="number"
                min="0"
                step="0.5"
                value={form.monthly_hours_limit}
                onChange={(e) => set("monthly_hours_limit", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder={form.contract_type === "minijob" ? "43" : ""}
              />
            </div>
          </div>

          {/* Qualifikationen */}
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1.5">
              Qualifikationen
            </label>
            {/* Chips */}
            {qualifications.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {qualifications.map((q) => (
                  <span
                    key={q}
                    className="flex items-center gap-1 text-xs px-2 py-1 rounded-full"
                    style={{
                      backgroundColor: "rgb(var(--ctp-blue) / 0.12)",
                      color: "rgb(var(--ctp-blue))",
                    }}
                  >
                    {q}
                    <button
                      type="button"
                      onClick={() => removeQual(q)}
                      className="opacity-70 hover:opacity-100"
                    >
                      <X size={10} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {/* Input */}
            <div className="flex gap-2">
              <input
                value={qualInput}
                onChange={(e) => setQualInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addQual(qualInput);
                  }
                }}
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                placeholder="Qualifikation eingeben + Enter"
              />
            </div>
            {/* Suggestions */}
            <div className="flex flex-wrap gap-1 mt-1.5">
              {QUALIFICATION_SUGGESTIONS.filter(
                (q) => !qualifications.includes(q)
              ).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => addQual(q)}
                  className="text-xs px-2 py-0.5 rounded-full border border-dashed border-border text-muted-foreground hover:border-blue-400 hover:text-foreground transition-colors"
                >
                  + {q}
                </button>
              ))}
            </div>
          </div>

          {/* Erweitert (aufklappbar) */}
          <div className="border border-border rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-muted-foreground hover:bg-muted/50"
            >
              <span>Erweiterte Einstellungen</span>
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            {showAdvanced && (
              <div className="px-4 pb-4 space-y-3 border-t border-border pt-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Jahresgehaltsgrenze (€)
                    </label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.annual_salary_limit}
                      onChange={(e) => set("annual_salary_limit", e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none"
                    />
                    {form.contract_type === "minijob" && (
                      <p className="text-xs text-muted-foreground mt-0.5">Minijob 2025: 6.672 €</p>
                    )}
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Urlaubstage / Jahr
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={form.vacation_days}
                      onChange={(e) => set("vacation_days", e.target.value)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
            >
              {mutation.isPending
                ? "Speichern…"
                : isEdit
                ? "Änderungen speichern"
                : "Mitarbeiter anlegen"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl text-sm border border-border text-muted-foreground hover:bg-muted"
            >
              Abbrechen
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── EmployeesPage ────────────────────────────────────────────────── */
export default function EmployeesPage() {
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [showInactive, setShowInactive] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [linking, setLinking] = useState<Employee | null>(null);

  const { data: employees = [], isLoading } = useQuery<Employee[]>({
    queryKey: ["employees", showInactive],
    queryFn: () =>
      employeesApi.list(!showInactive).then((r) => r.data),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => employeesApi.deactivate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      toast.success("Mitarbeiter deaktiviert");
    },
    onError: () => toast.error("Fehler beim Deaktivieren"),
  });

  const reactivateMutation = useMutation({
    mutationFn: (id: string) => employeesApi.update(id, { is_active: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      toast.success("Mitarbeiter reaktiviert");
    },
    onError: () => toast.error("Fehler beim Reaktivieren"),
  });

  // Group by contract type for display
  const active = employees.filter((e) => e.is_active);
  const inactive = employees.filter((e) => !e.is_active);

  const contractGroups: Record<string, Employee[]> = {};
  for (const emp of active) {
    const ct = emp.contract_type;
    if (!contractGroups[ct]) contractGroups[ct] = [];
    contractGroups[ct].push(emp);
  }
  const contractOrder = ["full_time", "part_time", "minijob"];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-2xl font-bold text-foreground flex-1">Mitarbeiter</h1>
        <div className="flex items-center gap-2">
          {/* Active/inactive toggle */}
          <button
            onClick={() => setShowInactive(!showInactive)}
            className={`text-sm px-3 py-1.5 rounded-xl border transition-colors ${
              showInactive
                ? "border-border bg-muted text-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {showInactive ? "Alle anzeigen" : "Inaktive zeigen"}
          </button>

          {/* Create button (Admin only) */}
          {isAdmin && (
            <button
              onClick={() => setCreating(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium text-white"
              style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
            >
              <Plus size={14} />
              <span className="hidden sm:inline">Mitarbeiter anlegen</span>
              <span className="sm:hidden">Neu</span>
            </button>
          )}
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>
          <span className="font-semibold text-foreground">{active.length}</span> aktiv
        </span>
        {Object.entries(contractGroups).map(([ct, emps]) => (
          <span key={ct}>
            <span className="font-medium" style={{ color: CONTRACT_COLORS[ct] }}>
              {emps.length}
            </span>{" "}
            {CONTRACT_LABELS[ct] ?? ct}
          </span>
        ))}
      </div>

      {isLoading ? (
        <div className="text-muted-foreground text-sm py-12 text-center">
          Lade Mitarbeiter…
        </div>
      ) : (
        <div className="space-y-6">
          {/* Active employees by group */}
          {contractOrder
            .filter((ct) => contractGroups[ct]?.length > 0)
            .map((ct) => (
              <div key={ct}>
                <div
                  className="text-xs font-semibold uppercase tracking-wider mb-2 px-1"
                  style={{ color: CONTRACT_COLORS[ct] }}
                >
                  {CONTRACT_LABELS[ct]} ({contractGroups[ct].length})
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {contractGroups[ct].map((emp) => (
                    <EmployeeCard
                      key={emp.id}
                      emp={emp}
                      isAdmin={isAdmin}
                      onEdit={() => setEditing(emp)}
                      onLink={() => setLinking(emp)}
                      onDeactivate={() => {
                        if (confirm(`${emp.first_name} ${emp.last_name} wirklich deaktivieren?`)) {
                          deactivateMutation.mutate(emp.id);
                        }
                      }}
                    />
                  ))}
                </div>
              </div>
            ))}

          {/* Empty state */}
          {active.length === 0 && (
            <div className="bg-card rounded-xl border border-border p-12 text-center">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"
                style={{
                  backgroundColor: "rgb(var(--ctp-blue) / 0.12)",
                  color: "rgb(var(--ctp-blue))",
                }}
              >
                <UserCheck size={28} />
              </div>
              <div className="font-medium text-foreground mb-1">Keine Mitarbeiter</div>
              {isAdmin && (
                <button
                  onClick={() => setCreating(true)}
                  className="mt-3 px-4 py-2 rounded-xl text-sm font-medium text-white"
                  style={{ backgroundColor: "rgb(var(--ctp-blue))" }}
                >
                  <Plus size={13} className="inline mr-1" />
                  Ersten Mitarbeiter anlegen
                </button>
              )}
            </div>
          )}

          {/* Inactive section */}
          {showInactive && inactive.length > 0 && (
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider mb-2 px-1 text-muted-foreground">
                Inaktiv ({inactive.length})
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {inactive.map((emp) => (
                  <EmployeeCard
                    key={emp.id}
                    emp={emp}
                    isAdmin={isAdmin}
                    inactive
                    onEdit={() => setEditing(emp)}
                    onReactivate={() => reactivateMutation.mutate(emp.id)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {creating && (
        <EmployeeModal
          onClose={() => setCreating(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ["employees"] })}
        />
      )}
      {editing && (
        <EmployeeModal
          employee={editing}
          onClose={() => setEditing(null)}
          onSaved={() => qc.invalidateQueries({ queryKey: ["employees"] })}
        />
      )}
      {linking && (
        <LinkAccountModal
          employee={linking}
          onClose={() => setLinking(null)}
          onSaved={() => qc.invalidateQueries({ queryKey: ["employees"] })}
        />
      )}
    </div>
  );
}

/* ── EmployeeCard ─────────────────────────────────────────────────── */
function EmployeeCard({
  emp,
  isAdmin,
  inactive,
  onEdit,
  onLink,
  onDeactivate,
  onReactivate,
}: {
  emp: Employee;
  isAdmin: boolean;
  inactive?: boolean;
  onEdit: () => void;
  onLink?: () => void;
  onDeactivate?: () => void;
  onReactivate?: () => void;
}) {
  const color = CONTRACT_COLORS[emp.contract_type] ?? "rgb(var(--ctp-overlay0))";

  return (
    <div
      className={`bg-card rounded-xl border border-border p-4 space-y-3 transition-opacity ${
        inactive ? "opacity-60" : ""
      }`}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 text-white"
          style={{ backgroundColor: color + " / 0.8)" }}
        >
          <span style={{ color: "white" }}>
            {emp.first_name[0]}
            {emp.last_name[0]}
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-foreground truncate">
            {emp.first_name} {emp.last_name}
          </div>
          <span
            className="text-xs px-2 py-0.5 rounded-full font-medium inline-block mt-0.5"
            style={{
              color,
              backgroundColor: color.replace(")", " / 0.12)").replace("rgb(", "rgb("),
            }}
          >
            {CONTRACT_LABELS[emp.contract_type] ?? emp.contract_type}
          </span>
        </div>

        {/* Action buttons (Admin only) */}
        {isAdmin && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={onEdit}
              className="p-2 rounded-lg hover:bg-muted text-muted-foreground"
              title="Bearbeiten"
            >
              <Pencil size={13} />
            </button>
            {onLink && (
              <button
                onClick={onLink}
                className="p-2 rounded-lg hover:bg-muted text-muted-foreground"
                title={emp.user_id ? "Login-Account verwalten" : "Login-Account verknüpfen"}
                style={emp.user_id ? { color: "rgb(var(--ctp-green))" } : {}}
              >
                <Link size={13} />
              </button>
            )}
            {!inactive && onDeactivate && (
              <button
                onClick={onDeactivate}
                className="p-2 rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-500"
                title="Deaktivieren"
              >
                <UserX size={13} />
              </button>
            )}
            {inactive && onReactivate && (
              <button
                onClick={onReactivate}
                className="p-2 rounded-lg hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-500"
                title="Reaktivieren"
              >
                <UserCheck size={13} />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Contact */}
      {(emp.email || emp.phone) && (
        <div className="space-y-1">
          {emp.email && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Mail size={12} className="shrink-0" />
              <span className="truncate">{emp.email}</span>
            </div>
          )}
          {emp.phone && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Phone size={12} className="shrink-0" />
              <span>{emp.phone}</span>
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-3 pt-1 border-t border-border text-xs text-muted-foreground">
        {emp.monthly_hours_limit && (
          <div className="flex items-center gap-1">
            <Clock size={11} />
            <span>{emp.monthly_hours_limit} h/Mo</span>
          </div>
        )}
        <div className="flex items-center gap-1">
          <Euro size={11} />
          <span>{emp.hourly_rate?.toFixed(2)} €/h</span>
        </div>
        {isAdmin && (
          <div className="ml-auto text-xs">
            {emp.vacation_days} Urlaubstage
          </div>
        )}
      </div>

      {/* Qualifications */}
      {emp.qualifications?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {emp.qualifications.map((q: string) => (
            <span
              key={q}
              className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
            >
              {q}
            </span>
          ))}
        </div>
      )}

      {/* Linked account indicator */}
      {isAdmin && (
        <div className="text-xs text-muted-foreground flex items-center gap-1">
          <span
            className={`w-1.5 h-1.5 rounded-full inline-block ${
              emp.user_id ? "bg-emerald-500" : "bg-amber-400"
            }`}
          />
          {emp.user_id ? "Login-Account verknüpft" : "Kein Login-Account"}
        </div>
      )}
    </div>
  );
}
