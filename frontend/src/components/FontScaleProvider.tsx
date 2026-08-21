"use client";

// Global font-scale preference: fetched once from the backend on mount,
// applied by scaling the root element's font-size (every Tailwind
// text-* utility is rem-based, so this rescales the whole app for free),
// and re-saved to the backend whenever the NavBar control changes it. See
// docs/superpowers/specs/2026-08-21-ui-font-scale-design.md.

import { createContext, useContext, useEffect, useState } from "react";
import { getPreferences, updatePreferences } from "@/lib/api";

// The 5 fixed stops the NavBar control cycles through. The backend only
// enforces the [0.85, 1.3] range (config_repository.FONT_SCALE_MIN/MAX) —
// picking discrete steps instead of a free slider is a frontend-only
// choice.
export const FONT_SCALE_LEVELS = [0.85, 0.925, 1.0, 1.15, 1.3];
const DEFAULT_FONT_SCALE = 1.0;

interface FontScaleContextValue {
  fontScale: number;
  setFontScale: (scale: number) => void;
}

const FontScaleContext = createContext<FontScaleContextValue | null>(null);

export function FontScaleProvider({ children }: { children: React.ReactNode }) {
  const [fontScale, setFontScaleState] = useState(DEFAULT_FONT_SCALE);

  useEffect(() => {
    let cancelled = false;
    getPreferences()
      .then((prefs) => {
        if (!cancelled) setFontScaleState(prefs.font_scale);
      })
      .catch(() => {
        // Backend unreachable, or preference unset — stay on the default.
        // Must never block page render.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    document.documentElement.style.fontSize = `${fontScale * 100}%`;
  }, [fontScale]);

  function setFontScale(scale: number) {
    const previous = fontScale;
    setFontScaleState(scale);
    updatePreferences(scale).catch(() => {
      // Save failed — revert so the displayed scale matches what's
      // actually persisted server-side.
      setFontScaleState(previous);
    });
  }

  return <FontScaleContext.Provider value={{ fontScale, setFontScale }}>{children}</FontScaleContext.Provider>;
}

export function useFontScale(): FontScaleContextValue {
  const ctx = useContext(FontScaleContext);
  if (!ctx) throw new Error("useFontScale must be used within a FontScaleProvider");
  return ctx;
}
