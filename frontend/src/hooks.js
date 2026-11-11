import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";

// Fetch hook with loading / error state and a manual reload.
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true }));
    api.get(path)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
  }, [path]);
  useEffect(load, [load, ...deps]);
  return { ...state, reload: load };
}
