import { useState, useEffect, useCallback } from 'react';

// Minimal global UI-language switch (EN | VI). Deliberately not React Context: every consumer
// just needs the current 2-letter code and a setter, and a module-level pub/sub avoids having to
// wrap the whole app tree in a provider for something this small.
//
// Scope note: this currently drives the global shell only (Header, Sidebar, AlertBellDropdown,
// StationContextBar). Individual route pages still carry their own hardcoded EN/VI copy and do
// not yet read this hook -- translating each page's content is tracked as follow-up work done
// alongside that page's own layout refactor, not a side effect of this toggle.
const STORAGE_KEY = 'edgeflow_ui_lang';

const readInitial = () => {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === 'vi' ? 'vi' : 'en';
  } catch {
    return 'en';
  }
};

let currentLang = readInitial();
let listeners = [];

export function useLanguage() {
  const [lang, setLangState] = useState(currentLang);

  useEffect(() => {
    listeners.push(setLangState);
    return () => {
      listeners = listeners.filter((l) => l !== setLangState);
    };
  }, []);

  const setLang = useCallback((next) => {
    currentLang = next;
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // private browsing / storage blocked -- the toggle still works for this session
    }
    listeners.forEach((l) => l(next));
  }, []);

  return [lang, setLang];
}
