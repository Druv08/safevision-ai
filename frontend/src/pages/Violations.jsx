import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { LuDownload, LuSearch, LuX, LuInbox, LuChevronRight, LuImageOff, LuTrash2, LuCheck, LuCircleCheck } from "react-icons/lu";
import API, { apiError } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { SOURCE_LABEL, STATUS_META, TYPE_OPTIONS } from "../theme";
import {
  PageHeader, Alert, EmptyState, Pagination, SeverityBadge, StatusBadge, Dialog, ConfirmDialog, Spinner,
} from "../components/ui";

const PAGE_SIZE = 20;
const FILTER_KEYS = ["type", "status", "source", "from", "to", "q"];

// <input type="date"> gives a local calendar day; the API wants instants.
const startOfDay = (d) => new Date(`${d}T00:00`).toISOString();
const startOfNextDay = (d) => {
  const t = new Date(`${d}T00:00`);
  t.setDate(t.getDate() + 1);
  return t.toISOString();
};
const fmt = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });

function Violations() {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const p = (k) => params.get(k) || "";
  const page = Number(params.get("page")) || 1;
  const sort = p("sort") || "newest";
  // Older links used ?highlight=<id>.
  const selectedId = p("id") || p("highlight");

  const [data, setData] = useState(null); // { key, rows, count }
  const [error, setError] = useState(null); // { key, message }
  const [search, setSearch] = useState(p("q"));
  const [exporting, setExporting] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);

  const update = useCallback((changes, { resetPage = true } = {}) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(changes)) { if (v) next.set(k, v); else next.delete(k); }
      if (resetPage && !("page" in changes)) next.delete("page");
      return next;
    }, { replace: true });
  }, [setParams]);

  // Debounce the search box into the URL.
  useEffect(() => {
    const t = setTimeout(() => { if (search.trim() !== (params.get("q") || "")) update({ q: search.trim() }); }, 300);
    return () => clearTimeout(t);
  }, [search, params, update]);

  const query = useMemo(() => {
    const q = { page, page_size: PAGE_SIZE, sort };
    if (p("type")) q.type = p("type");
    if (p("status")) q.status = p("status");
    if (p("source")) q.source = p("source");
    if (p("from")) q.date_from = startOfDay(p("from"));
    if (p("to")) q.date_to = startOfNextDay(p("to"));
    if (p("q")) q.q = p("q");
    return q;
  }, [params]); // eslint-disable-line react-hooks/exhaustive-deps
  const key = JSON.stringify(query);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      API.get("/violations", { params: query })
        .then((r) => { if (!cancelled) { setData({ key, rows: r.data.violations, count: r.data.count }); setError(null); } })
        .catch((e) => { if (!cancelled) setError({ key, message: apiError(e, "Could not load violations.") }); });
    load();
    const id = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [key, query, reloadTick]);

  const loading = !data || data.key !== key;
  const rows = data?.rows ?? [];
  const filtered = FILTER_KEYS.some((k) => params.get(k));
  const pageError = error && error.key === key ? error.message : "";

  // Selected record: from the current page, or handed over by the link that opened it.
  const selected = rows.find((v) => v.id === selectedId)
    || (location.state?.violation?.id === selectedId ? location.state.violation : null);

  const reload = () => setReloadTick((t) => t + 1);

  const downloadCSV = async () => {
    setExporting(true);
    try {
      const r = await API.get("/download-violations", { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `violations-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast("CSV export downloaded.");
    } catch (e) {
      // Error bodies arrive as a Blob because of responseType.
      let msg = apiError(e, "Export failed.");
      try { msg = JSON.parse(await e.response.data.text()).detail || msg; } catch { /* not JSON */ }
      toast(msg, "danger");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Violations"
        description="Every PPE violation with its evidence. Review, acknowledge and close incidents."
        actions={
          <button onClick={downloadCSV} disabled={exporting} className="btn btn-secondary">
            {exporting ? <Spinner /> : <LuDownload />} Export CSV
          </button>
        }
      />

      {/* Filters */}
      <div className="card p-3 sm:p-4 mb-4">
        <div className="grid gap-3 grid-cols-2 md:grid-cols-3 xl:grid-cols-[2fr_repeat(5,1fr)]">
          <label className="col-span-2 md:col-span-3 xl:col-span-1">
            <span className="label">Search</span>
            <span className="relative block">
              <LuSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-subtle pointer-events-none" aria-hidden="true" />
              <input
                type="search"
                value={search}
                maxLength={100}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Type, status, note, model…"
                className="input pl-9"
              />
            </span>
          </label>
          <Select label="Type" value={p("type")} onChange={(v) => update({ type: v })} options={TYPE_OPTIONS} all="All types" />
          <Select label="Status" value={p("status")} onChange={(v) => update({ status: v })}
            options={Object.entries(STATUS_META).map(([value, m]) => ({ value, label: m.label }))} all="Any status" />
          <Select label="Source" value={p("source")} onChange={(v) => update({ source: v })}
            options={Object.entries(SOURCE_LABEL).map(([value, label]) => ({ value, label }))} all="All sources" />
          <label>
            <span className="label">From</span>
            <input type="date" value={p("from")} max={p("to") || undefined} onChange={(e) => update({ from: e.target.value })} className="input" />
          </label>
          <label>
            <span className="label">To</span>
            <input type="date" value={p("to")} min={p("from") || undefined} onChange={(e) => update({ to: e.target.value })} className="input" />
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 mt-3 pt-3 border-t border-line">
          <p className="text-sm text-muted tabular-nums" aria-live="polite">
            {loading && !data ? "Loading…" : `${data?.count ?? 0} ${filtered ? "matching" : "total"} record${data?.count === 1 ? "" : "s"}`}
          </p>
          <div className="flex items-center gap-2">
            {filtered && (
              <button className="btn btn-ghost btn-sm" onClick={() => { setSearch(""); update(Object.fromEntries(FILTER_KEYS.map((k) => [k, ""]))); }}>
                <LuX /> Clear filters
              </button>
            )}
            <label className="flex items-center gap-2 text-sm text-muted">
              <span className="sr-only sm:not-sr-only">Sort</span>
              <select value={sort} onChange={(e) => update({ sort: e.target.value === "newest" ? "" : e.target.value })} className="input h-8 w-auto">
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      {/* Results */}
      <section className="card overflow-hidden" aria-label="Violation records" aria-busy={loading}>
        {pageError && !rows.length ? (
          <div className="p-4"><Alert onRetry={reload}>{pageError}</Alert></div>
        ) : loading && !data ? (
          <div className="p-4 space-y-3">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton h-11" />)}</div>
        ) : rows.length === 0 ? (
          <EmptyState icon={LuInbox} title={filtered ? "No violations match these filters" : "No violations recorded yet"}>
            {filtered ? "Try removing a filter or widening the date range." : "Violations from image, video and live camera analysis appear here."}
          </EmptyState>
        ) : (
          <div className={loading ? "opacity-60 transition-opacity" : ""}>
            {pageError && <div className="p-3 border-b border-line"><Alert tone="warning" onRetry={reload}>{pageError} Showing the last loaded page.</Alert></div>}

            {/* Desktop table */}
            <div className="hidden lg:block overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th>Detected</th><th>Violation</th><th>Severity</th><th>Source</th>
                    <th>Confidence</th><th>Status</th><th className="hidden xl:table-cell">ID</th>
                    <th><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((v) => (
                    <tr key={v.id} onClick={() => update({ id: v.id }, { resetPage: false })} className="cursor-pointer">
                      <td className="tabular-nums text-muted whitespace-nowrap">{fmt(v.created_at)}</td>
                      <td className="font-medium whitespace-nowrap">{v.violation_type}</td>
                      <td><SeverityBadge severity={v.severity} /></td>
                      <td className="text-muted whitespace-nowrap">{SOURCE_LABEL[v.source] ?? v.source}</td>
                      <td className="tabular-nums">{(v.confidence * 100).toFixed(1)}%</td>
                      <td><StatusBadge status={v.status} /></td>
                      <td className="hidden xl:table-cell font-mono text-xs text-subtle" title={v.id}>{v.id.slice(0, 8)}</td>
                      <td className="text-right">
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={(e) => { e.stopPropagation(); update({ id: v.id }, { resetPage: false }); }}
                          aria-label={`Open details for ${v.violation_type} at ${fmt(v.created_at)}`}
                        >
                          Details <LuChevronRight />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <ul className="lg:hidden divide-y divide-line">
              {rows.map((v) => (
                <li key={v.id}>
                  <button onClick={() => update({ id: v.id }, { resetPage: false })} className="w-full text-left px-4 py-3.5 hover:bg-surface-2 flex items-start gap-3">
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-sm truncate">{v.violation_type}</p>
                        <SeverityBadge severity={v.severity} />
                      </div>
                      <p className="text-xs text-muted tabular-nums">{fmt(v.created_at)} · {SOURCE_LABEL[v.source] ?? v.source}</p>
                      <div className="flex items-center justify-between gap-2">
                        <StatusBadge status={v.status} />
                        <span className="text-xs tabular-nums text-muted">{(v.confidence * 100).toFixed(1)}% confidence</span>
                      </div>
                    </div>
                    <LuChevronRight className="text-subtle mt-1 flex-shrink-0" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>

            {(data?.count ?? 0) > PAGE_SIZE && (
              <Pagination page={page} pageSize={PAGE_SIZE} total={data.count} onChange={(n) => update({ page: String(n) })} />
            )}
          </div>
        )}
      </section>

      <ViolationDialog
        key={selectedId}
        id={selectedId}
        violation={selected}
        isAdmin={isAdmin}
        onClose={() => update({ id: "", highlight: "" }, { resetPage: false })}
        onChanged={reload}
      />
    </div>
  );
}

function Select({ label, value, onChange, options, all }) {
  return (
    <label>
      <span className="label">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="input">
        <option value="">{all}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

function ViolationDialog({ id, violation, isAdmin, onClose, onChanged }) {
  const toast = useToast();
  const [record, setRecord] = useState(violation);
  const [evidence, setEvidence] = useState({ state: "loading" });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const v = record || violation; // a later page refresh can supply the row

  // Fetching evidence is audit-logged by the backend, so it happens once per opened record.
  useEffect(() => {
    if (!id || !violation?.screenshot_path) return;
    let cancelled = false;
    API.get(`/violations/${id}/evidence`)
      .then((r) => !cancelled && setEvidence({ state: "ready", url: r.data.url }))
      .catch((e) => !cancelled && setEvidence({ state: "error", message: apiError(e, "Could not load the screenshot.") }));
    return () => { cancelled = true; };
  }, [id, violation?.screenshot_path]);

  const setStatus = async (status) => {
    setBusy(status);
    try {
      const r = await API.patch(`/violations/${id}`, { status, ...(note.trim() ? { note: note.trim() } : {}) });
      setRecord(r.data);
      setNote("");
      toast(status === "closed" ? "Violation closed." : "Violation acknowledged.");
      onChanged();
    } catch (e) {
      toast(apiError(e, "Could not update the violation."), "danger");
    } finally {
      setBusy("");
    }
  };

  const remove = async () => {
    setBusy("delete");
    try {
      await API.delete(`/violations/${id}`);
      toast("Violation and its evidence were deleted.");
      setConfirmDelete(false);
      onClose();
      onChanged();
    } catch (e) {
      toast(apiError(e, "Could not delete the violation."), "danger");
    } finally {
      setBusy("");
    }
  };

  const open = Boolean(id);
  if (!open) return null;

  return (
    <>
      <Dialog
        open={open && !confirmDelete}
        onClose={onClose}
        width="44rem"
        title={v ? v.violation_type : "Violation"}
        description={v ? `Detected ${fmt(v.created_at)}` : undefined}
        footer={
          v && isAdmin ? (
            <>
              <button className="btn btn-danger mr-auto" onClick={() => setConfirmDelete(true)} disabled={!!busy}>
                <LuTrash2 /> Delete
              </button>
              {v.status === "new" && (
                <button className="btn btn-secondary" onClick={() => setStatus("acknowledged")} disabled={!!busy}>
                  {busy === "acknowledged" ? <Spinner /> : <LuCheck />} Acknowledge
                </button>
              )}
              {v.status !== "closed" && (
                <button className="btn btn-primary" onClick={() => setStatus("closed")} disabled={!!busy}>
                  {busy === "closed" ? <Spinner /> : <LuCircleCheck />} Close incident
                </button>
              )}
            </>
          ) : (
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
          )
        }
      >
        {!v ? (
          <Alert tone="info">This record isn't on the current page. Clear the filters or go back to the first page to find it.</Alert>
        ) : (
          <div className="space-y-5">
            <div className="rounded-lg border border-line bg-canvas overflow-hidden flex items-center justify-center min-h-48">
              {!v.screenshot_path ? (
                <EmptyState icon={LuImageOff} title="No evidence image" className="py-8">This record was saved without a screenshot.</EmptyState>
              ) : evidence.state === "loading" ? (
                <div className="skeleton w-full h-64 rounded-none" />
              ) : evidence.state === "error" ? (
                <div className="p-4 w-full"><Alert>{evidence.message}</Alert></div>
              ) : (
                <img
                  src={evidence.url}
                  alt={`Evidence frame for ${v.violation_type}`}
                  className="max-h-[50vh] w-auto"
                  onError={() => setEvidence({ state: "error", message: "The evidence link expired. Close and reopen this record." })}
                />
              )}
            </div>

            <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 text-sm">
              <Field label="Severity"><SeverityBadge severity={v.severity} /></Field>
              <Field label="Status"><StatusBadge status={v.status} /></Field>
              <Field label="Confidence"><span className="tabular-nums">{(v.confidence * 100).toFixed(1)}%</span></Field>
              <Field label="Source">{SOURCE_LABEL[v.source] ?? v.source}</Field>
              <Field label="Model"><span className="font-mono text-xs break-all">{v.model_version || "—"}</span></Field>
              <Field label="Record ID"><span className="font-mono text-xs break-all">{v.id}</span></Field>
              {v.acknowledged_by && <Field label="Acknowledged by"><span className="font-mono text-xs break-all">{v.acknowledged_by}</span></Field>}
              {v.closed_by && <Field label="Closed by"><span className="font-mono text-xs break-all">{v.closed_by}</span></Field>}
              {v.note && <div className="col-span-full"><Field label="Note">{v.note}</Field></div>}
            </dl>

            {isAdmin && v.status !== "closed" && (
              <label className="block">
                <span className="label">Add a note (optional, saved with the status change)</span>
                <textarea rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} className="input" placeholder="e.g. Supervisor spoke with the crew at gate 3" />
              </label>
            )}
            {!isAdmin && <p className="text-xs text-muted">Read-only access. An admin can acknowledge, close or delete records.</p>}
          </div>
        )}
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        danger
        busy={busy === "delete"}
        title="Delete this violation?"
        confirmLabel="Delete permanently"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={remove}
      >
        The record and its evidence screenshot will be removed. The deletion is written to the audit log. This cannot be undone.
      </ConfirmDialog>
    </>
  );
}

function Field({ label, children }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted mb-1">{label}</dt>
      <dd className="text-fg">{children}</dd>
    </div>
  );
}

export default Violations;
