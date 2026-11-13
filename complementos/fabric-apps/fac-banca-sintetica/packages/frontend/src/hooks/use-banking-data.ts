import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  describeLoadError,
  loadBaseData,
  loadMonthCellsFor,
  type BaseData,
} from '@/data/warehouse';
import { sucursalIdsOf, type MonthCell } from '@/lib/banking-metrics';

export type Load<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; message: string };

export interface BankingData {
  base: Load<BaseData>;
  /** Serie mensual de la provincia elegida (de todas si no hay filtro). */
  monthly: Load<MonthCell[]>;
  reload: () => void;
  /** Reintenta la serie mensual de la provincia elegida. */
  retryMonthly: () => void;
}

/**
 * Carga las agregaciones del Warehouse. El filtro de canal se aplica en memoria;
 * el de provincia se empuja al Warehouse para la serie mensual y se guarda en
 * caché por provincia.
 */
export function useBankingData(provincia: string | null): BankingData {
  const [base, setBase] = useState<Load<BaseData>>({ status: 'loading' });
  const [byProvince, setByProvince] = useState<
    Record<string, Load<MonthCell[]>>
  >({});
  const [attempt, setAttempt] = useState(0);
  // Invalida respuestas de una carga anterior cuando se pulsa «Reintentar».
  const generation = useRef(0);

  useEffect(() => {
    const current = ++generation.current;
    loadBaseData().then(
      (data) => {
        if (generation.current === current) setBase({ status: 'ready', data });
      },
      (error: unknown) => {
        if (generation.current === current)
          setBase({ status: 'error', message: describeLoadError(error) });
      }
    );
  }, [attempt]);

  const baseData = base.status === 'ready' ? base.data : null;
  const cached = provincia !== null ? byProvince[provincia] : undefined;

  useEffect(() => {
    if (provincia === null || baseData === null || cached !== undefined) return;
    const current = generation.current;
    const update = (value: Load<MonthCell[]>) => {
      if (generation.current === current)
        setByProvince((state) => ({ ...state, [provincia]: value }));
    };
    update({ status: 'loading' });
    loadMonthCellsFor(
      baseData.months,
      sucursalIdsOf(baseData.sucursales, provincia)
    ).then(
      (data) => update({ status: 'ready', data }),
      (error: unknown) =>
        update({ status: 'error', message: describeLoadError(error) })
    );
  }, [provincia, baseData, cached]);

  const monthly = useMemo<Load<MonthCell[]>>(() => {
    if (base.status !== 'ready') return base;
    if (provincia === null)
      return { status: 'ready', data: base.data.monthCells };
    return cached ?? { status: 'loading' };
  }, [base, cached, provincia]);

  const reload = useCallback(() => {
    setBase({ status: 'loading' });
    setByProvince({});
    setAttempt((n) => n + 1);
  }, []);

  const retryMonthly = useCallback(() => {
    if (provincia === null) return;
    setByProvince((state) => {
      const rest = { ...state };
      delete rest[provincia];
      return rest;
    });
  }, [provincia]);

  return { base, monthly, reload, retryMonthly };
}

