'use client';
import { useQuery } from '@tanstack/react-query';
import { api, catalogSchema, objectSchema, pageSchema, type CatalogKind } from './api/client';
import { z } from 'zod';
export const useCatalog = (kind: CatalogKind, offset = 0) =>
  useQuery({
    queryKey: ['catalog', kind, offset],
    queryFn: ({ signal }) =>
      api(`/api/research/catalog?kind=${kind}&limit=30&offset=${offset}`, catalogSchema, {
        signal,
      }),
    staleTime: 60000,
  });
export const useObject = (path: string | undefined) =>
  useQuery({
    queryKey: ['object', path],
    queryFn: ({ signal }) => api(path!, objectSchema, { signal }),
    enabled: !!path,
    staleTime: Infinity,
  });
export const usePage = (path: string | undefined) =>
  useQuery({
    queryKey: ['page', path],
    queryFn: ({ signal }) => api(path!, pageSchema, { signal }),
    enabled: !!path,
    staleTime: Infinity,
  });
export const useArray = (path: string | undefined) =>
  useQuery({
    queryKey: ['array', path],
    queryFn: ({ signal }) => api(path!, z.array(objectSchema), { signal }),
    enabled: !!path,
    staleTime: Infinity,
  });

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
export function useSelection(kind: CatalogKind, preferred?: string) {
  const [offset, setOffset] = useState(0);
  const catalog = useCatalog(kind, offset);
  const params = useSearchParams();
  const [chosen, setChosen] = useState<string | null>(null);
  const items = catalog.data?.items ?? [];
  const id =
    chosen ??
    params.get('run') ??
    items.find((i) => preferred && i.label.includes(preferred))?.id ??
    items[0]?.id ??
    '';
  return {
    catalog,
    items,
    id,
    select: setChosen,
    offset,
    next: () => {
      setOffset((o) => o + 30);
      setChosen(null);
    },
    previous: () => {
      setOffset((o) => Math.max(0, o - 30));
      setChosen(null);
    },
  };
}
