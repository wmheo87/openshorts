import { useRef, useState } from 'react';
import { t, useUiLocale } from './runtime.js';
export default function LocalizedFileInput({ onChange, ...props }) {
  useUiLocale();
  const input = useRef(null); const [names, setNames] = useState([]);
  return <span className="inline-flex flex-wrap items-center gap-2 max-w-full">
    <input {...props} ref={input} type="file" className="sr-only" onChange={event => { setNames([...event.target.files].map(file => file.name)); onChange?.(event); }} />
    <button type="button" className="btn-quiet px-3 py-1.5 text-xs" disabled={props.disabled} onClick={() => input.current?.click()}>{t(props.multiple ? 'Choose files' : 'Choose file')}</button>
    <span className="text-xs break-all">{names.length ? names.join(', ') : t('No file selected')}</span>
  </span>;
}
