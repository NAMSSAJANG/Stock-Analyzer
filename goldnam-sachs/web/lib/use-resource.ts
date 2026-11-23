"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Envelope } from "./api";
export function useResource<T>(path: string | null) {
  const [result, setResult] = useState<Envelope<T> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let alive = true;
    async function load() {
      if (!path) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError("");
      setResult(null);
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const r = await api<T>(path, { signal: controller.signal });
          if (alive) {
            setResult(r);
            setLoading(false);
            setRetrying(false);
            if (r.meta.as_of)
              localStorage.setItem(
                "goldnam_last_viewed",
                new Date().toISOString(),
              );
          }
          return;
        } catch (e) {
          if (!alive || controller.signal.aborted) return;
          if (attempt < 2 && (!(e instanceof ApiError) || e.status === 503)) {
            setRetrying(true);
            await new Promise((r) => setTimeout(r, 600 * (attempt + 1)));
            continue;
          }
          setError(e instanceof Error ? e.message : "연결 없음");
          setLoading(false);
          setRetrying(false);
        }
      }
    }
    void load();
    return () => {
      alive = false;
      controller.abort();
    };
  }, [path, revision]);
  return { result, loading, error, retrying, reload };
}
