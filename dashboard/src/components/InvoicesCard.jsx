import LocalizedDiagnostic from '../i18n/LocalizedDiagnostic';
import { getUiLocale, formatUiDate, t as uiT, useUiLocale } from "../i18n/runtime.js";
import React, { useState, useEffect } from 'react';
import { FileText, ExternalLink, Download, Loader2 } from 'lucide-react';
import { apiJson } from '../lib/api';

// Legally valid invoices for the account's Stripe charges, issued by
// AgentLedger. The backend hands us pre-signed public links, so "View" and
// "Download" open directly without any extra auth from the browser.
const STATUS_CLASS = {
  paid: 'badge-ok',
  partially_paid: 'badge-warn',
  overdue: 'badge-warn',
};

function formatDate(iso) {
  if (!iso) return '';
  return formatUiDate(iso, { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC' });
}

function formatMoney(amount, currency) {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${amount} ${currency}`;
  try {
    return new Intl.NumberFormat(getUiLocale(), { style: 'currency', currency: (currency || 'EUR').toUpperCase() }).format(n);
  } catch (_) {
    return `${n.toFixed(2)} ${currency}`;
  }
}

export default function InvoicesCard() {
  useUiLocale();
  const [invoices, setInvoices] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    apiJson('/api/billing/invoices')
      .then((d) => { if (!cancelled) setInvoices(Array.isArray(d.invoices) ? d.invoices : []); })
      .catch((e) => { if (!cancelled) { setError(e?.detail || 'Could not load invoices.'); setInvoices([]); } });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="card p-6">
      <h3 className="font-display lowercase text-lg text-ink mb-1 flex items-center gap-2">
        <FileText size={16} className="text-brass" />{uiT(" Invoices")}</h3>
      <p className="text-muted text-sm mb-4 lowercase">{uiT("Legally valid invoices for every charge on this account.")}</p>

      {invoices === null ? (
        <div className="flex items-center gap-2 text-muted text-sm py-4">
          <Loader2 size={16} className="animate-spin text-brass" />{uiT(" Loading invoices…")}</div>
      ) : error ? (
        <p className="text-sm text-warn">{<LocalizedDiagnostic value={error} error />}</p>
      ) : invoices.length === 0 ? (
        <p className="text-sm text-muted">{uiT("No invoices yet. They appear here after your first payment — give it a few minutes if you just subscribed.")}</p>
      ) : (
        <ul className="divide-y divide-rule">
          {invoices.map((inv) => (
            <li key={inv.doc_number || inv.public_url} className="py-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="text-ink font-medium font-mono text-xs">{uiT(inv.doc_number)}</div>
                <div className="text-muted text-xs mt-0.5">
                  {uiT(formatDate(inv.doc_date))} · <span className="text-ink2">{uiT(formatMoney(inv.total, inv.currency))}</span>
                  {inv.status && (
                    <span className={`ml-2 ${STATUS_CLASS[inv.status] || 'badge-warn'}`}>{uiT(inv.status.replace(/_/g, ' '))}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {inv.public_url && (
                  <a href={inv.public_url} target="_blank" rel="noopener noreferrer" className="btn-ghost px-3 py-1.5 text-xs">
                    <ExternalLink size={14} />{uiT(" View")}</a>
                )}
                {inv.pdf_url && (
                  <a href={inv.pdf_url} target="_blank" rel="noopener noreferrer" className="btn-ghost px-3 py-1.5 text-xs">
                    <Download size={14} />{uiT(" PDF")}</a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
