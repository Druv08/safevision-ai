import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LuPlus, LuPencil, LuTrash2, LuSend, LuBell, LuRefreshCw } from "react-icons/lu";
import API, { apiError } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { PageHeader, SectionTitle, Alert, EmptyState, Dialog, ConfirmDialog, Spinner } from "../components/ui";

const CHANNELS = { whatsapp: "WhatsApp", webhook: "Webhook" };
const LANGUAGES = { en: "English", hi: "हिन्दी (Hindi)" };
const DELIVERY = {
  sent: { label: "Sent", tone: "tone-ok" },
  logged: { label: "Logged only", tone: "tone-warning" },
  failed: { label: "Failed", tone: "tone-danger" },
  sending: { label: "Sending", tone: "tone-info" },
};
const PROVIDER = {
  meta: "WhatsApp Cloud API (Meta)",
  twilio: "Twilio",
  log: "not configured: messages are written to the server log",
};

function Alerts() {
  const { isAdmin } = useAuth();
  const toast = useToast();
  const [data, setData] = useState(null); // { recipients, whatsapp_provider, alerts }
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(null); // null | {} (new) | recipient
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([API.get("/alerts/recipients"), API.get("/alerts")]);
      setData({ ...r.data, alerts: a.data.alerts });
      setError("");
    } catch (e) {
      setError(apiError(e, "Could not load alert settings."));
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    const t = setTimeout(load, 0);
    return () => clearTimeout(t);
  }, [isAdmin, load]);

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Alerts" />
        <Alert tone="info">Only admins can see and change who receives alerts.</Alert>
      </div>
    );
  }

  const run = async (key, fn) => {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy("");
    }
  };

  const test = (r) => run(r.id, async () => {
    try {
      const res = (await API.post(`/alerts/recipients/${r.id}/test`)).data;
      if (res.status === "sent") toast(`Test alert sent to ${r.name}.`);
      else if (res.status === "logged") toast("WhatsApp is not configured: the test message was written to the server log.", "warning");
      else toast(`Test failed: ${res.error}`, "danger");
    } catch (e) {
      toast(apiError(e, "Could not send the test."), "danger");
    }
  });

  const toggle = (r) => run(r.id, async () => {
    try {
      await API.patch(`/alerts/recipients/${r.id}`, { enabled: !r.enabled });
      load();
    } catch (e) {
      toast(apiError(e, "Could not update the recipient."), "danger");
    }
  });

  const remove = () => run(deleting.id, async () => {
    try {
      await API.delete(`/alerts/recipients/${deleting.id}`);
      toast(`${deleting.name} will no longer get alerts.`);
      setDeleting(null);
      load();
    } catch (e) {
      toast(apiError(e, "Could not delete the recipient."), "danger");
    }
  });

  return (
    <div>
      <PageHeader
        title="Alerts"
        description="One message per violation episode from the cameras, to every enabled recipient, in their language. Messages contain no image; the link opens the record for signed-in users."
        actions={
          <>
            <button className="btn btn-secondary" onClick={load}><LuRefreshCw /> Refresh</button>
            <button className="btn btn-primary" onClick={() => setEditing({})}><LuPlus /> Add recipient</button>
          </>
        }
      />

      {error && <Alert className="mb-4" onRetry={load}>{error}</Alert>}
      {data && (
        <Alert tone={data.whatsapp_provider === "log" ? "warning" : "info"} className="mb-4" title="WhatsApp provider">
          {PROVIDER[data.whatsapp_provider] ?? data.whatsapp_provider}.
          {data.whatsapp_provider === "log" && " Set WHATSAPP_META_TOKEN and WHATSAPP_META_PHONE_NUMBER_ID, or the TWILIO_* variables, in backend/.env."}
        </Alert>
      )}

      <section className="card min-w-0" aria-label="Recipients">
        <div className="p-4 sm:p-5 pb-0 sm:pb-0"><SectionTitle title="Recipients" /></div>
        {!data ? (
          <div className="p-5 space-y-3">{[0, 1].map((i) => <div key={i} className="skeleton h-10" />)}</div>
        ) : !data.recipients.length ? (
          <EmptyState icon={LuBell} title="Nobody gets alerts yet"
            action={<button className="btn btn-primary btn-sm" onClick={() => setEditing({})}><LuPlus /> Add recipient</button>}>
            Add a supervisor's WhatsApp number or a webhook (e.g. a Teams or Slack relay).
          </EmptyState>
        ) : (
          <div className="overflow-x-auto mt-3">
            <table className="table">
              <thead><tr><th>Name</th><th>Channel</th><th>Address</th><th>Language</th><th>On</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {data.recipients.map((r) => (
                  <tr key={r.id} className={r.enabled ? "" : "opacity-60"}>
                    <td className="font-medium">{r.name}</td>
                    <td>{CHANNELS[r.channel]}</td>
                    <td className="font-mono text-xs break-all max-w-72">{r.address}</td>
                    <td>{LANGUAGES[r.language]}</td>
                    <td>
                      <input type="checkbox" checked={r.enabled} onChange={() => toggle(r)} disabled={busy === r.id}
                        aria-label={`Alerts on for ${r.name}`} className="accent-[var(--primary)]" />
                    </td>
                    <td className="text-right whitespace-nowrap">
                      <button className="btn btn-ghost btn-sm" onClick={() => test(r)} disabled={busy === r.id}>
                        {busy === r.id ? <Spinner /> : <LuSend />} Test
                      </button>
                      <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setEditing(r)} aria-label={`Edit ${r.name}`}><LuPencil /></button>
                      <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setDeleting(r)} aria-label={`Delete ${r.name}`}><LuTrash2 /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card min-w-0 mt-4" aria-label="Recent alerts">
        <div className="p-4 sm:p-5 pb-0 sm:pb-0"><SectionTitle title="Recent alerts" description="Last 50 deliveries, newest first" /></div>
        {!data ? (
          <div className="p-5"><div className="skeleton h-24" /></div>
        ) : !data.alerts.length ? (
          <p className="text-sm text-muted p-5 pt-3">No alerts sent yet.</p>
        ) : (
          <div className="overflow-x-auto mt-3">
            <table className="table">
              <thead><tr><th>Time</th><th>Recipient</th><th>Channel</th><th>Status</th><th>Record</th></tr></thead>
              <tbody>
                {data.alerts.map((a) => (
                  <tr key={a.id}>
                    <td className="tabular-nums text-muted whitespace-nowrap">{new Date(a.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</td>
                    <td>{a.recipient_name ?? "Deleted recipient"}</td>
                    <td>{CHANNELS[a.channel] ?? a.channel}</td>
                    <td>
                      <span className={`badge ${DELIVERY[a.status]?.tone ?? "tone-neutral"}`} title={a.error || undefined}>
                        <span className="dot" />{DELIVERY[a.status]?.label ?? a.status}
                      </span>
                      {a.error && <p className="text-xs text-muted mt-1 max-w-72 truncate" title={a.error}>{a.error}</p>}
                    </td>
                    <td><Link to={`/violations?id=${a.violation_id}`} className="btn btn-ghost btn-sm">Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {editing && <RecipientDialog recipient={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
      <ConfirmDialog
        open={Boolean(deleting)}
        danger
        busy={busy === deleting?.id}
        title={`Delete ${deleting?.name}?`}
        confirmLabel="Delete recipient"
        onCancel={() => setDeleting(null)}
        onConfirm={remove}
      >
        They stop getting alerts. Past deliveries stay in the log.
      </ConfirmDialog>
    </div>
  );
}

function RecipientDialog({ recipient, onClose, onSaved }) {
  const toast = useToast();
  const isNew = !recipient.id;
  const [form, setForm] = useState({
    name: recipient.name || "",
    channel: recipient.channel || "whatsapp",
    address: recipient.address || "",
    language: recipient.language || "en",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    const body = { ...form, name: form.name.trim(), address: form.address.trim() };
    try {
      if (isNew) await API.post("/alerts/recipients", body);
      else await API.patch(`/alerts/recipients/${recipient.id}`, body);
      toast(isNew ? "Recipient added." : "Recipient updated.");
      onSaved();
    } catch (err) {
      setError(apiError(err, "Could not save the recipient."));
    } finally {
      setSaving(false);
    }
  };

  const whatsapp = form.channel === "whatsapp";
  return (
    <Dialog
      open
      onClose={onClose}
      title={isNew ? "Add recipient" : `Edit ${recipient.name}`}
      width="30rem"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" type="submit" form="recipient-form" disabled={saving}>
            {saving && <Spinner />} {isNew ? "Add" : "Save"}
          </button>
        </>
      }
    >
      <form id="recipient-form" onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="label">Name</span>
          <input className="input" required maxLength={100} value={form.name} onChange={set("name")} placeholder="Site supervisor, north gate" />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="label">Channel</span>
            <select className="input" value={form.channel} onChange={set("channel")}>
              {Object.entries(CHANNELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="label">Message language</span>
            <select className="input" value={form.language} onChange={set("language")}>
              {Object.entries(LANGUAGES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        </div>
        <label className="block">
          <span className="label">{whatsapp ? "WhatsApp number" : "Webhook URL"}</span>
          <input className="input font-mono" required maxLength={500} value={form.address} onChange={set("address")} spellCheck={false}
            type={whatsapp ? "tel" : "url"} placeholder={whatsapp ? "+919812345678" : "https://example.com/hooks/safevision"} />
          <span className="block text-xs text-muted mt-1">
            {whatsapp
              ? "International format with +. The person should agree to receive alerts, and must have messaged your WhatsApp number in the last 24 hours unless you use an approved template."
              : "Receives a JSON POST. Signed with HMAC-SHA256 in X-SafeVision-Signature when ALERT_WEBHOOK_SECRET is set."}
          </span>
        </label>
        {error && <Alert>{error}</Alert>}
      </form>
    </Dialog>
  );
}

export default Alerts;
