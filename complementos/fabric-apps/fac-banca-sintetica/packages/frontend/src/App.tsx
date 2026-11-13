import { CircleAlert, CircleCheck, Database } from 'lucide-react';
import { useMemo, useState } from 'react';

import { AppHeader } from '@/components/dashboard/app-header';
import { BranchTable } from '@/components/dashboard/branch-table';
import { MonthlyChart, ProvinceChart } from '@/components/dashboard/charts';
import { FiltersBar } from '@/components/dashboard/filters-bar';
import { KpiCards } from '@/components/dashboard/kpi-cards';
import type { BaseData } from '@/data/warehouse';
import { useBankingData } from '@/hooks/use-banking-data';
import {
  branchRows,
  computeKpis,
  filterBranchCells,
  provinceTotals,
  reconcileWithSummary,
  type Filters,
  type MonthCell,
} from '@/lib/banking-metrics';

const SKELETON_BLOCKS = ['kpi-1', 'kpi-2', 'kpi-3', 'kpi-4', 'kpi-5'];

function LoadingState() {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-400">
      <p className="flex items-center gap-200 text-300 text-muted-foreground">
        <Database aria-hidden="true" className="icon-size-200" />
        Consultando el Warehouse…
      </p>
      <div className="grid grid-cols-1 gap-300 sm:grid-cols-2 lg:grid-cols-5">
        {SKELETON_BLOCKS.map((id) => (
          <div key={id} className="h-24 animate-pulse rounded-2xl bg-muted" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-400 lg:grid-cols-2">
        <div className="h-96 animate-pulse rounded-2xl bg-muted" />
        <div className="h-96 animate-pulse rounded-2xl bg-muted" />
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-300 rounded-2xl border border-destructive bg-card p-500"
    >
      <p className="flex items-center gap-200 text-400 font-semibold text-destructive">
        <CircleAlert aria-hidden="true" className="icon-size-300" />
        No se pudieron cargar los datos
      </p>
      <p className="text-300 text-foreground">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg bg-primary px-400 py-200 text-300 font-medium text-primary-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        Reintentar
      </button>
    </div>
  );
}

interface DashboardProps {
  base: BaseData;
  monthCells: readonly MonthCell[];
  monthBusy: boolean;
  monthError: string | null;
  onRetryMonth: () => void;
  filters: Filters;
  onFilters: (filters: Filters) => void;
}

function Dashboard({
  base,
  monthCells,
  monthBusy,
  monthError,
  onRetryMonth,
  filters,
  onFilters,
}: DashboardProps) {
  const canales = useMemo(
    () => [...new Set(base.branchCells.map((c) => c.canal))].sort(),
    [base.branchCells]
  );
  const kpis = useMemo(
    () => computeKpis(filterBranchCells(base.branchCells, base.sucursales, filters)),
    [base, filters]
  );
  const rows = useMemo(
    () => branchRows(base.branchCells, base.sucursales, filters),
    [base, filters]
  );
  const provinces = useMemo(
    () => provinceTotals(base.branchCells, base.sucursales, filters.canal),
    [base, filters.canal]
  );
  const reconciliation = useMemo(
    () => reconcileWithSummary(base.monthCells, base.summary),
    [base]
  );

  return (
    <>
      <FiltersBar
        filters={filters}
        canales={canales}
        sucursales={base.sucursales}
        onChange={onFilters}
      />
      <KpiCards kpis={kpis} />

      {monthError ? (
        <ErrorState message={monthError} onRetry={onRetryMonth} />
      ) : null}

      <div className="grid grid-cols-1 gap-400 lg:grid-cols-2">
        <MonthlyChart
          cells={monthCells}
          canal={filters.canal}
          metric="transacciones"
          title="Transacciones por mes y canal"
          description="Cada color es un canal."
          busy={monthBusy}
        />
        <MonthlyChart
          cells={monthCells}
          canal={filters.canal}
          metric="monto"
          title="Monto por mes y canal"
          description="Millones de colones; cada color es un canal."
          busy={monthBusy}
        />
      </div>

      <div className="grid grid-cols-1 gap-400 lg:grid-cols-5">
        <ProvinceChart
          totals={provinces}
          selected={filters.provincia}
          className="lg:col-span-2"
        />
        <BranchTable rows={rows} className="lg:col-span-3" />
      </div>

      <p
        className="flex items-center gap-200 text-200 text-muted-foreground"
        role="note"
      >
        {reconciliation.differences.length === 0 ? (
          <>
            <CircleCheck aria-hidden="true" className="icon-size-200 text-primary" />
            Control de cuadre: las {reconciliation.checked} filas de
            transacciones.resumen_mes_canal coinciden con lo calculado desde
            transacciones.fact_transaccion.
          </>
        ) : (
          <>
            <CircleAlert aria-hidden="true" className="icon-size-200 text-destructive" />
            Control de cuadre: {reconciliation.differences.length} de{' '}
            {reconciliation.checked} filas del resumen no coinciden con el hecho.
          </>
        )}
      </p>
    </>
  );
}

function App() {
  const [filters, setFilters] = useState<Filters>({
    canal: null,
    provincia: null,
  });
  const { base, monthly, reload, retryMonthly } = useBankingData(filters.provincia);

  return (
    <div className="min-h-full bg-secondary">
      <AppHeader />
      <main className="mx-auto flex max-w-7xl flex-col gap-400 px-400 py-400">
        {base.status === 'loading' ? <LoadingState /> : null}
        {base.status === 'error' ? (
          <ErrorState message={base.message} onRetry={reload} />
        ) : null}
        {base.status === 'ready' ? (
          <Dashboard
            base={base.data}
            monthCells={monthly.status === 'ready' ? monthly.data : []}
            monthBusy={monthly.status === 'loading'}
            monthError={monthly.status === 'error' ? monthly.message : null}
            onRetryMonth={retryMonthly}
            filters={filters}
            onFilters={setFilters}
          />
        ) : null}
      </main>
    </div>
  );
}

export default App;


