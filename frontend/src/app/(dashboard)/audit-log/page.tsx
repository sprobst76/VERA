"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { de } from "date-fns/locale";
import {
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Loader2,
} from "lucide-react";
import { auditLogApi, api } from "@/lib/api";
import { useAuthStore } from "@/store/auth";

/* ── Constants ─────────────────────────────────────────────────────────────── */

const PAGE_SIZE = 50;

const ENTITY_LABELS: Record<string, string> = {
  shift: "Dienst",
  employee: "Mitarbeiter",
  payroll: "Abrechnung",
  absence: "Abwesenheit",
  contract_history: "Vertragshistorie",
};

const ACTION_CONFIG: Record<string, { label: string; color: string }> = {
  create: { label: "angelegt", color: "var(--ctp-green)" },
  update: { label: "geändert", color: "var(--ctp-blue)" },
  delete: { label: "gelöscht", color: "var(--ctp-red)" },
  confirm: { label: "geändert", color: "var(--ctp-blue)" },
  claim: { label: "geändert", color: "var(--ctp-blue)" },
  time_correction_submit: { label: "geändert", color: "var(--ctp-blue)" },
  time_correction_review: { label: "geändert", color: "var(--ctp-blue)" },
};

const PAYROLL_AUDIT_FIELDS = ["actual_hours", "base_wage", "total_gross"] as const;

/* ── Types ──────────────────────────────────────────────────────────────────── */

interface AuditLogEntry {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string;
}

interface AuditLogPage {
  items: AuditLogEntry[];
  total: number;
}

interface UserRecord {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

/* ── DiffLine sub-component ─────────────────────────────────────────────────── */

function DiffLine({
  field,
  before,
  after,
}: {
  field: string;
  before: unknown;
  after: unknown;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground w-28 shrink-0">{field}</span>
      <span
        className="line-through"
        style={{ color: "rgb(var(--ctp-red))" }}
      >
        {String(before ?? "—")}
      </span>
      <span className="text-muted-foreground mx-2">{"→"}</span>
      <span style={{ color: "rgb(var(--ctp-green))" }}>
        {String(after ?? "—")}
      </span>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────────────────── */

export default function AuditLogPage() {
  const { user } = useAuthStore();

  const [entityType, setEntityType] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [page, setPage] = useState(1);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  /* ── Access guard ──────────────────────────────────────────────────────── */
  if (user && user.role !== "admin") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
        <div
          className="w-12 h-12 rounded-2xl flex items-center justify-center"
          style={{ backgroundColor: "rgb(var(--ctp-red) / 0.12)" }}
        >
          <ClipboardList size={24} style={{ color: "rgb(var(--ctp-red))" }} />
        </div>
        <div className="font-medium text-foreground">Kein Zugriff</div>
        <div className="text-xs text-muted-foreground">
          Nur Administratoren haben Zugriff auf den Audit-Log.
        </div>
      </div>
    );
  }

  /* ── Data fetching ─────────────────────────────────────────────────────── */
  const { data, isLoading, isError } = useQuery<AuditLogPage>({
    queryKey: ["audit-log", entityType, fromDate, toDate, page],
    queryFn: () =>
      auditLogApi
        .list({
          entity_type: entityType || undefined,
          from_date: fromDate || undefined,
          to_date: toDate || undefined,
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        })
        .then((r) => r.data),
  });

  const { data: usersData = [] } = useQuery<UserRecord[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users").then((r) => r.data),
  });

  const userMap = new Map<string, string>(
    usersData.map((u) => [
      u.id,
      u.first_name && u.last_name
        ? `${u.first_name} ${u.last_name}`
        : u.email,
    ])
  );

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const offset = (page - 1) * PAGE_SIZE;
  const isLastPage = offset + items.length >= total;
  const hasFilters = entityType !== "" || fromDate !== "" || toDate !== "";

  function resetFilters() {
    setEntityType("");
    setFromDate("");
    setToDate("");
    setPage(1);
  }

  function handleEntityTypeChange(v: string) {
    setEntityType(v);
    setPage(1);
  }

  function handleFromDateChange(v: string) {
    setFromDate(v);
    setPage(1);
  }

  function handleToDateChange(v: string) {
    setToDate(v);
    setPage(1);
  }

  /* ── Render ────────────────────────────────────────────────────────────── */
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Audit-Log</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Unveränderliche Aufzeichnung aller Schreiboperationen
        </p>
      </div>

      {/* FilterBar */}
      <div className="bg-card rounded-xl border border-border p-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Entität</label>
            <select
              value={entityType}
              onChange={(e) => handleEntityTypeChange(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
            >
              <option value="">Alle Entitäten</option>
              {Object.entries(ENTITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Von</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => handleFromDateChange(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Bis</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => handleToDateChange(e.target.value)}
              className="px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-sm"
            />
          </div>
          {hasFilters && (
            <button
              onClick={resetFilters}
              className="text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
            >
              Zurücksetzen
            </button>
          )}
        </div>
      </div>

      {/* Results count */}
      {!isLoading && !isError && (
        <p className="text-xs text-muted-foreground">{total} Einträge</p>
      )}

      {/* AuditTable */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm gap-2">
            <Loader2 size={16} className="animate-spin" /> Wird geladen...
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3 text-center">
            <div className="font-medium text-foreground">
              Audit-Log konnte nicht geladen werden
            </div>
            <div className="text-xs text-muted-foreground">
              Seite neu laden oder Administrator kontaktieren
            </div>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: "rgb(var(--ctp-blue) / 0.12)" }}
            >
              <ClipboardList size={24} style={{ color: "rgb(var(--ctp-blue))" }} />
            </div>
            <div className="text-center">
              <div className="font-medium text-foreground">Keine Einträge gefunden</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Passe die Filter an oder wahle einen anderen Zeitraum
              </div>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground">
                    Zeitpunkt
                  </th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground">
                    Benutzer
                  </th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground">
                    Aktion
                  </th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground">
                    Entität
                  </th>
                  <th className="text-left px-4 py-3 text-xs text-muted-foreground">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const config = ACTION_CONFIG[item.action] ?? {
                    label: item.action,
                    color: "var(--ctp-overlay0)",
                  };
                  const userName = item.user_id
                    ? userMap.get(item.user_id) ?? item.user_id.slice(0, 8) + "..."
                    : "—";
                  const hasDetails =
                    item.old_values !== null || item.new_values !== null;
                  const isExpanded = expandedRow === item.id;

                  return (
                    <>
                      <tr
                        key={item.id}
                        className="border-b border-border last:border-0 hover:bg-muted/40 transition-colors"
                        style={
                          idx % 2 === 1
                            ? { backgroundColor: "rgb(var(--ctp-surface0) / 0.3)" }
                            : {}
                        }
                      >
                        {/* Zeitpunkt */}
                        <td className="px-4 py-3 text-sm text-foreground whitespace-nowrap">
                          {format(new Date(item.created_at), "dd.MM.yyyy HH:mm", {
                            locale: de,
                          })}
                        </td>

                        {/* Benutzer */}
                        <td className="px-4 py-3 text-sm text-foreground">
                          {userName}
                        </td>

                        {/* Aktion badge */}
                        <td className="px-4 py-3">
                          <span
                            className="px-2 py-0.5 rounded-full text-xs font-medium"
                            style={{
                              backgroundColor: `rgb(${config.color} / 0.12)`,
                              color: `rgb(${config.color})`,
                            }}
                          >
                            {config.label}
                          </span>
                        </td>

                        {/* Entität */}
                        <td className="px-4 py-3">
                          <div className="text-sm text-foreground">
                            {ENTITY_LABELS[item.entity_type] ?? item.entity_type}
                          </div>
                          {item.entity_id && (
                            <div className="text-xs text-muted-foreground">
                              {item.entity_id.slice(0, 8)}...
                            </div>
                          )}
                        </td>

                        {/* Details expand */}
                        <td className="px-4 py-3">
                          {hasDetails && (
                            <button
                              onClick={() =>
                                setExpandedRow(isExpanded ? null : item.id)
                              }
                              className="text-muted-foreground hover:text-foreground transition-colors"
                              title={
                                isExpanded
                                  ? "Details ausblenden"
                                  : "Details anzeigen"
                              }
                            >
                              {isExpanded ? (
                                <ChevronUp size={16} />
                              ) : (
                                <ChevronDown size={16} />
                              )}
                            </button>
                          )}
                        </td>
                      </tr>

                      {/* Expanded diff row */}
                      {isExpanded && (
                        <tr key={`${item.id}-expanded`} className="border-b border-border last:border-0">
                          <td colSpan={5} className="px-4 pb-3 pt-0">
                            <div className="bg-background rounded-lg border border-border p-3 text-xs font-mono space-y-1">
                              {item.entity_type === "payroll" &&
                              item.old_values !== null &&
                              item.new_values !== null ? (
                                <>
                                  {PAYROLL_AUDIT_FIELDS.map((field) => (
                                    <DiffLine
                                      key={field}
                                      field={field}
                                      before={item.old_values?.[field]}
                                      after={item.new_values?.[field]}
                                    />
                                  ))}
                                </>
                              ) : (
                                <div className="space-y-1">
                                  {item.old_values !== null &&
                                    item.new_values !== null &&
                                    Object.keys({
                                      ...item.old_values,
                                      ...item.new_values,
                                    }).map((field) => (
                                      <DiffLine
                                        key={field}
                                        field={field}
                                        before={item.old_values?.[field]}
                                        after={item.new_values?.[field]}
                                      />
                                    ))}
                                  {(item.old_values === null ||
                                    item.new_values === null) && (
                                    <div className="text-muted-foreground">
                                      {item.old_values !== null
                                        ? JSON.stringify(item.old_values, null, 2)
                                        : JSON.stringify(item.new_values, null, 2)}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* PaginationBar */}
      {!isLoading && !isError && total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {offset + 1}–{offset + items.length} von {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-sm transition-colors hover:bg-muted/40 ${
                page === 1 ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              <ChevronLeft size={16} /> Zurück
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={isLastPage}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-sm transition-colors hover:bg-muted/40 ${
                isLastPage ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              Weiter <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
