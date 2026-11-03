import { t as uiT, useUiLocale } from "../i18n/runtime.js";
import React from 'react';
import { KeyRound, ArrowRight } from 'lucide-react';

// Banner for advanced tools (AI Shorts, AI Agent) that use fal.ai + ElevenLabs.
// These are BYOK: the plan covers the script/orchestration, the user brings their
// own keys for the premium generation. If they have no plan yet, also nudge trial.
export default function AdvancedBanner({ needsPlan, onKeys, providerLabel = 'fal.ai + ElevenLabs', scriptNotice = 'Script & orchestration are included in your plan.' }) {
  useUiLocale();
  return (
    <div className="card mx-3 sm:mx-6 mt-3 px-3.5 sm:px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 shrink-0 animate-fade">
      <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 text-sm min-w-0">
        <KeyRound size={16} className="shrink-0 text-warn mt-0.5 sm:mt-0" />
        <div className="text-ink2 lowercase leading-relaxed min-w-0">
          <span className="font-medium text-ink">{uiT("Advanced tool.")}</span>{uiT(' ')}
          {needsPlan
            ? <>{uiT("Sign in with ")}<span className="font-medium text-ink">{uiT("Google")}</span>{uiT(" to unlock free. This tool also uses your own ")}<span className="font-medium text-ink normal-case">{uiT(providerLabel)}</span>{uiT(" keys (you pay those providers).")}</>
            : <>{uiT("AI video & voice generation use your own ")}<span className="font-medium text-ink normal-case">{uiT(providerLabel)}</span>{uiT(" keys — add them in Settings. ")}{uiT(scriptNotice)}</>}
        </div>
      </div>
      <button
        onClick={needsPlan ? () => { window.location.hash = '#/pricing'; } : onKeys}
        className="btn-quiet shrink-0 text-xs px-3 py-1.5 w-full sm:w-auto"
      >
        {needsPlan ? <>{uiT("See plans ")}<ArrowRight size={14} /></> : uiT('Add keys')}
      </button>
    </div>
  );
}
