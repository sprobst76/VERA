"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shiftSwapsApi, shiftsApi, employeesApi } from "@/lib/api";
import { ArrowLeftRight, Clock, X, Check, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import { de } from "date-fns/locale";
import toast from "react-hot-toast";

interface SwapOffer {
  id: string;
  shift_id: string;
  offering_employee_id: string;
  status: string;
  note: string | null;
  expires_at: string;
  accepted_by_employee_id: string | null;
  review_note: string | null;
}

interface EmployeeLite {
  id: string;
  first_name: string;
  last_name: string;
}

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  open:              { color: "rgb(var(--ctp-blue))",   backgroundColor: "rgb(var(--ctp-blue) / 0.12)" },
  pending_approval:  { color: "rgb(var(--ctp-peach))",  backgroundColor: "rgb(var(--ctp-peach) / 0.12)" },
  completed:         { color: "rgb(var(--ctp-green))",  backgroundColor: "rgb(var(--ctp-green) / 0.12)" },
  withdrawn:         { color: "rgb(var(--ctp-overlay1))", backgroundColor: "rgb(var(--ctp-surface1) / 0.6)" },
  expired:           { color: "rgb(var(--ctp-overlay1))", backgroundColor: "rgb(var(--ctp-surface1) / 0.6)" },
  denied:            { color: "rgb(var(--ctp-red))",    backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
  cancelled_system:  { color: "rgb(var(--ctp-red))",    backgroundColor: "rgb(var(--ctp-red) / 0.12)" },
};

const STATUS_LABELS: Record<string, string> = {
  open: "Offen",
  pending_approval: "Wartet auf Genehmigung",
  completed: "Vollzogen",
  withdrawn: "Zurückgezogen",
  expired: "Abgelaufen",
  denied: "Abgelehnt",
  cancelled_system: "Automatisch storniert",
};

function apiErrorMessage(e: unknown, fallback: string): string {
  const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return msg ?? fallback;
}

function OfferCard({
  offer, employeeMap, ownId, isPrivileged, onChanged,
}: {
  offer: SwapOffer;
  employeeMap: Record<string, EmployeeLite>;
  ownId: string | null;
  isPrivileged: boolean;
  onChanged: () => void;
}) {
  const [showDenyNote, setShowDenyNote] = useState(false);
  const [denyNote, setDenyNote] = useState("");

  const { data: shift } = useQuery({
    queryKey: ["shift", offer.shift_id],
    queryFn: () => shiftsApi.get(offer.shift_id).then((r) => r.data),
  });

  const acceptMutation = useMutation({
    mutationFn: () => shiftSwapsApi.accept(offer.id),
    onSuccess: (res) => {
      onChanged();
      toast.success(res.data.status === "pending_approval" ? "Angenommen – wartet auf Genehmigung" : "Dienst übernommen!");
    },
    onError: (e: unknown) => toast.error(apiErrorMessage(e, "Übernahme fehlgeschlagen")),
  });

  const withdrawMutation = useMutation({
    mutationFn: () => shiftSwapsApi.withdraw(offer.id),
    onSuccess: () => { onChanged(); toast.success("Angebot zurückgezogen"); },
    onError: (e: unknown) => toast.error(apiErrorMessage(e, "Zurückziehen fehlgeschlagen")),
  });

  const reviewMutation = useMutation({
    mutationFn: (data: { approved: boolean; note?: string }) => shiftSwapsApi.review(offer.id, data),
    onSuccess: (_res, vars) => {
      onChanged();
      toast.success(vars.approved ? "Tausch genehmigt" : "Tausch abgelehnt");
      setShowDenyNote(false);
    },
    onError: (e: unknown) => toast.error(apiErrorMessage(e, "Aktion fehlgeschlagen")),
  });

  const offering = employeeMap[offer.offering_employee_id];
  const offeringName = offering ? `${offering.first_name} ${offering.last_name}` : "…";
  const isMine = offer.offering_employee_id === ownId;

  const canAccept = offer.status === "open" && !isMine && !isPrivileged;
  const canWithdraw = isMine && ["open", "pending_approval"].includes(offer.status) && !isPrivileged;
  const canWithdrawAsAdmin = isPrivileged && ["open", "pending_approval"].includes(offer.status);
  const canReview = isPrivileged && offer.status === "pending_approval";

  return (
    <div className="bg-card rounded-xl border border-border p-4 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium text-foreground">
          {shift
            ? `${format(parseISO(shift.date), "EEEE, d.M.", { locale: de })} · ${shift.start_time.slice(0, 5)}–${shift.end_time.slice(0, 5)}`
            : "Lade…"}
        </div>
        <span className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0" style={STATUS_STYLE[offer.status]}>
          {STATUS_LABELS[offer.status] ?? offer.status}
        </span>
      </div>

      <div className="text-xs text-muted-foreground">
        Angeboten von <span className="font-medium text-foreground">{offeringName}</span>
        {shift?.location && <> · {shift.location}</>}
      </div>

      {offer.note && (
        <div className="text-xs text-muted-foreground italic">&ldquo;{offer.note}&rdquo;</div>
      )}

      {offer.review_note && (
        <div className="text-xs text-muted-foreground">Begründung: {offer.review_note}</div>
      )}

      {offer.status === "open" && (
        <div className="text-xs text-muted-foreground flex items-center gap-1">
          <Clock size={11} />
          läuft ab {formatDistanceToNow(parseISO(offer.expires_at), { locale: de, addSuffix: true })}
        </div>
      )}

      {(canAccept || canWithdraw || canWithdrawAsAdmin || canReview) && (
        <div className="flex gap-2 flex-wrap pt-1">
          {canAccept && (
            <button
              onClick={() => acceptMutation.mutate()}
              disabled={acceptMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {acceptMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <ArrowLeftRight size={12} />}
              Übernehmen
            </button>
          )}
          {(canWithdraw || canWithdrawAsAdmin) && (
            <button
              onClick={() => withdrawMutation.mutate()}
              disabled={withdrawMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted disabled:opacity-50 transition-colors text-muted-foreground"
            >
              <X size={12} /> Zurückziehen
            </button>
          )}
          {canReview && !showDenyNote && (
            <>
              <button
                onClick={() => reviewMutation.mutate({ approved: true })}
                disabled={reviewMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50 transition-colors"
                style={{ backgroundColor: "rgb(var(--ctp-green) / 0.15)", color: "rgb(var(--ctp-green))" }}
              >
                <Check size={12} /> Genehmigen
              </button>
              <button
                onClick={() => setShowDenyNote(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted transition-colors text-muted-foreground"
              >
                <X size={12} /> Ablehnen
              </button>
            </>
          )}
        </div>
      )}

      {canReview && showDenyNote && (
        <div className="space-y-2 pt-1">
          <input
            type="text"
            value={denyNote}
            onChange={(e) => setDenyNote(e.target.value)}
            placeholder="Grund (optional)"
            className="w-full px-3 py-1.5 rounded-lg border border-border bg-background text-foreground text-xs"
          />
          <div className="flex gap-2">
            <button
              onClick={() => reviewMutation.mutate({ approved: false, note: denyNote || undefined })}
              disabled={reviewMutation.isPending}
              className="px-3 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
              style={{ backgroundColor: "rgb(var(--ctp-red) / 0.15)", color: "rgb(var(--ctp-red))" }}
            >
              Ablehnung bestätigen
            </button>
            <button
              onClick={() => setShowDenyNote(false)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted text-muted-foreground"
            >
              Abbrechen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ShiftSwapSection({
  ownEmployeeId, isPrivileged,
}: {
  ownEmployeeId: string | null;
  isPrivileged: boolean;
}) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(true);

  const { data: offers = [] } = useQuery<SwapOffer[]>({
    queryKey: ["shift-swap-offers"],
    queryFn: () => shiftSwapsApi.list().then((r) => r.data),
  });

  const { data: employees = [] } = useQuery<EmployeeLite[]>({
    queryKey: ["employees", "public-names"],
    queryFn: () => employeesApi.list(true).then((r) => r.data),
  });
  const employeeMap = Object.fromEntries(employees.map((e) => [e.id, e]));

  function refresh() {
    qc.invalidateQueries({ queryKey: ["shift-swap-offers"] });
    qc.invalidateQueries({ queryKey: ["shifts"] });
  }

  const relevantOffers = offers.filter((o) => {
    if (isPrivileged) return ["open", "pending_approval"].includes(o.status);
    if (o.offering_employee_id === ownEmployeeId) return ["open", "pending_approval"].includes(o.status);
    return o.status === "open";
  });

  const pendingApprovalCount = offers.filter((o) => o.status === "pending_approval").length;

  if (relevantOffers.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <ArrowLeftRight size={16} style={{ color: "rgb(var(--ctp-blue))" }} />
          <span className="font-semibold text-foreground">Tauschbörse</span>
          <span className="text-xs px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground">
            {relevantOffers.length}
          </span>
          {isPrivileged && pendingApprovalCount > 0 && (
            <span
              className="text-xs px-1.5 py-0.5 rounded-full font-medium"
              style={{ backgroundColor: "rgb(var(--ctp-peach) / 0.15)", color: "rgb(var(--ctp-peach))" }}
            >
              {pendingApprovalCount} wartet auf Genehmigung
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} className="text-muted-foreground" /> : <ChevronDown size={16} className="text-muted-foreground" />}
      </button>
      {expanded && (
        <div className="p-4 pt-0 space-y-3">
          {relevantOffers.map((offer) => (
            <OfferCard
              key={offer.id}
              offer={offer}
              employeeMap={employeeMap}
              ownId={ownEmployeeId}
              isPrivileged={isPrivileged}
              onChanged={refresh}
            />
          ))}
        </div>
      )}
    </div>
  );
}
