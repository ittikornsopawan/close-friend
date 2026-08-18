"use client";

import { useEffect, useState } from "react";

import { getPersonas } from "@/lib/api-client";
import type { Persona } from "@/lib/types";

export function usePersonas() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPersonas()
      .then((loaded) => {
        if (!cancelled) {
          setPersonas(loaded);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Couldn't load personas.");
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { personas, isLoading, error };
}
