import { t as uiT, useUiLocale } from "../i18n/runtime.js";
import React, { useState, useRef, useEffect } from 'react';
import { CreditCard, LogOut, Sparkles } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

// Header avatar + dropdown for signed-in cloud users: shows the email and gives
// access to Account & billing (manage subscription, top-ups) and Sign out.
// onUpgrade: opens the in-app plan picker for free users; without it the
// entry goes to the pricing page.
export default function ProfileMenu({ onUpgrade = null }) {
  useUiLocale();
  const { user, isManaged, plan, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  if (!user) return null;
  const initial = (user.email || '?').trim().charAt(0).toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={uiT("Account menu")}
        className="w-8 h-8 rounded-full bg-paper3 border border-rule hover:border-rule2 text-brass flex items-center justify-center text-sm font-medium transition-colors"
      >
        {uiT(initial)}
      </button>

      {open && (
        <div className="card absolute right-0 top-full mt-2 w-56 z-30 shadow-none overflow-hidden animate-fade">
          <div className="px-4 py-3 border-b border-rule">
            <p className="eyebrow">{uiT("Signed in as")}</p>
            <p className="text-sm text-ink truncate mt-0.5" title={uiT(user.email)}>{uiT(user.email)}</p>
          </div>
          {!isManaged && (
            <button
              onClick={() => { setOpen(false); window.location.hash = '#/pricing'; }}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm lowercase text-brass hover:bg-paper3 transition-colors"
            >
              <Sparkles size={16} />{uiT(" Start free")}</button>
          )}
          {isManaged && plan === 'free' && (
            <button
              onClick={() => {
                setOpen(false);
                if (onUpgrade) onUpgrade({ source: 'menu' });
                else window.location.hash = '#/pricing';
              }}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm lowercase text-brass hover:bg-paper3 transition-colors"
            >
              <Sparkles size={16} />{uiT(" Upgrade · no watermark")}</button>
          )}
          <button
            onClick={() => { setOpen(false); window.location.hash = '#/account'; }}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm lowercase text-ink2 hover:bg-paper3 transition-colors"
          >
            <CreditCard size={16} className="text-muted" />{uiT(" Account & billing")}</button>
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm lowercase text-ink2 hover:bg-paper3 transition-colors border-t border-rule"
          >
            <LogOut size={16} className="text-muted" />{uiT(" Sign out")}</button>
        </div>
      )}
    </div>
  );
}
