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

// Mirrors the last-known-good font_scale so the very first paint on a hard
// reload already renders at the right size, instead of flashing at 100%
// until the GET /preferences round-trip resolves (every rem-based Tailwind
// utility — p-*, w-*, gap-*, h-14, etc, not just text — reflows on that
// snap, so the flash is whole-UI, not just text).
const FONT_SCALE_STORAGE_KEY = "asterism-font-scale";

function readStoredFontScale(): number {
  if (typeof window === "undefined") return DEFAULT_FONT_SCALE;
  const raw = window.localStorage.getItem(FONT_SCALE_STORAGE_KEY);
  const value = raw === null ? NaN : Number(raw);
  return Number.isFinite(value) ? value : DEFAULT_FONT_SCALE;
}

function writeStoredFontScale(value: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FONT_SCALE_STORAGE_KEY, String(value));
}

interface FontScaleContextValue {
  fontScale: number;
  setFontScale: (scale: number) => void;
}

const FontScaleContext = createContext<FontScaleContextValue | null>(null);

export function FontScaleProvider({ children }: { children: React.ReactNode }) {
  // Initializer runs synchronously on the first render, so localStorage's
  // last-known value (if any) is already applied before paint — the backend
  // fetch below only reconciles afterward if it differs.
  const [fontScale, setFontScaleState] = useState(readStoredFontScale);

  useEffect(() => {
    let cancelled = false;
    getPreferences()
      .then((prefs) => {
        if (!cancelled) {
          setFontScaleState(prefs.font_scale);
          writeStoredFontScale(prefs.font_scale);
        }
      })
      .catch(() => {
        // Backend unreachable, or preference unset — stay on the
        // localStorage/default value. Must never block page render.
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
    writeStoredFontScale(scale);
    updatePreferences(scale).catch(() => {
      // Save failed — revert so the displayed scale matches what's
      // actually persisted server-side.
      setFontScaleState(previous);
      writeStoredFontScale(previous);
    });
  }

  return <FontScaleContext.Provider value={{ fontScale, setFontScale }}>{children}</FontScaleContext.Provider>;
}

export function useFontScale(): FontScaleContextValue {
  const ctx = useContext(FontScaleContext);
  if (!ctx) throw new Error("useFontScale must be used within a FontScaleProvider");
  return ctx;
}
