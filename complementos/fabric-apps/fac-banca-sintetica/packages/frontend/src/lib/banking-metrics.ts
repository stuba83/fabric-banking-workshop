/**
 * Cálculos puros sobre las agregaciones que devuelve el Warehouse.
 * Cada "celda" es el resultado de un GROUP BY canal, dirección; así los filtros
 * por canal y provincia se aplican aquí, sin volver a consultar.
 */

export interface Sucursal {
  sucursalId: string;
  nombre: string;
  provincia: string;
}

export interface Cell {
  canal: string;
  /** CREDITO = entrada de dinero; DEBITO = salida. */
  direccion: string;
  transacciones: number;
  /** Suma de magnitudes positivas (la dirección define el efecto). */
  monto: number;
}

export interface BranchCell extends Cell {
  sucursalId: string;
}

export interface MonthCell extends Cell {
  /** 'YYYY-MM' */
  mes: string;
}

export interface SummaryRow {
  mes: string;
  canal: string;
  transacciones: number;
  montoCreditos: number;
  montoDebitos: number;
}

export interface Filters {
  canal: string | null;
  provincia: string | null;
}

export interface Kpis {
  transacciones: number;
  monto: number;
  ticketPromedio: number;
  creditos: number;
  debitos: number;
  neto: number;
  canalPrincipal: { canal: string; participacion: number } | null;
}

export interface BranchRow {
  sucursalId: string;
  sucursal: string;
  provincia: string;
  transacciones: number;
  monto: number;
  ticketPromedio: number;
  creditos: number;
  debitos: number;
}

export interface MonthChannelTotal {
  mes: string;
  canal: string;
  transacciones: number;
  monto: number;
}

export interface ProvinceTotal {
  provincia: string;
  transacciones: number;
  monto: number;
}

const CREDITO = 'CREDITO';

export function sucursalIdsOf(
  sucursales: readonly Sucursal[],
  provincia: string | null
): string[] {
  return sucursales
    .filter((s) => provincia === null || s.provincia === provincia)
    .map((s) => s.sucursalId);
}

function sumBy<T>(items: readonly T[], pick: (item: T) => number): number {
  return items.reduce((total, item) => total + pick(item), 0);
}

function byCanal<T extends Cell>(cells: readonly T[], canal: string | null) {
  return canal === null ? cells : cells.filter((c) => c.canal === canal);
}

/** Celdas por sucursal que cumplen ambos filtros. */
export function filterBranchCells(
  cells: readonly BranchCell[],
  sucursales: readonly Sucursal[],
  filters: Filters
): BranchCell[] {
  const allowed = new Set(sucursalIdsOf(sucursales, filters.provincia));
  return byCanal(cells, filters.canal).filter((c) =>
    allowed.has(c.sucursalId)
  );
}

export function computeKpis(cells: readonly Cell[]): Kpis {
  const transacciones = sumBy(cells, (c) => c.transacciones);
  const monto = sumBy(cells, (c) => c.monto);
  const creditos = sumBy(
    cells.filter((c) => c.direccion === CREDITO),
    (c) => c.monto
  );
  const debitos = monto - creditos;

  const porCanal = new Map<string, number>();
  for (const c of cells) {
    porCanal.set(c.canal, (porCanal.get(c.canal) ?? 0) + c.transacciones);
  }
  const [canal, n] = [...porCanal.entries()].sort((a, b) => b[1] - a[1])[0] ?? [
    undefined,
    0,
  ];

  return {
    transacciones,
    monto,
    ticketPromedio: transacciones > 0 ? monto / transacciones : 0,
    creditos,
    debitos,
    neto: creditos - debitos,
    canalPrincipal:
      canal !== undefined && transacciones > 0
        ? { canal, participacion: n / transacciones }
        : null,
  };
}

/** Totales por mes y canal, ordenados por mes y luego por canal. */
export function monthChannelTotals(
  cells: readonly MonthCell[],
  canal: string | null
): MonthChannelTotal[] {
  const totals = new Map<string, MonthChannelTotal>();
  for (const c of byCanal(cells, canal)) {
    const key = `${c.mes}|${c.canal}`;
    const current = totals.get(key) ?? {
      mes: c.mes,
      canal: c.canal,
      transacciones: 0,
      monto: 0,
    };
    current.transacciones += c.transacciones;
    current.monto += c.monto;
    totals.set(key, current);
  }
  return [...totals.values()].sort(
    (a, b) => a.mes.localeCompare(b.mes) || a.canal.localeCompare(b.canal)
  );
}

export function branchRows(
  cells: readonly BranchCell[],
  sucursales: readonly Sucursal[],
  filters: Filters
): BranchRow[] {
  const filtered = filterBranchCells(cells, sucursales, filters);
  return sucursales
    .filter(
      (s) => filters.provincia === null || s.provincia === filters.provincia
    )
    .map((s) => {
      const own = filtered.filter((c) => c.sucursalId === s.sucursalId);
      const kpis = computeKpis(own);
      return {
        sucursalId: s.sucursalId,
        sucursal: s.nombre,
        provincia: s.provincia,
        transacciones: kpis.transacciones,
        monto: kpis.monto,
        ticketPromedio: kpis.ticketPromedio,
        creditos: kpis.creditos,
        debitos: kpis.debitos,
      };
    });
}

/** Totales por provincia; el filtro de provincia no se aplica (se resalta en el gráfico). */
export function provinceTotals(
  cells: readonly BranchCell[],
  sucursales: readonly Sucursal[],
  canal: string | null
): ProvinceTotal[] {
  const provinciaDe = new Map(
    sucursales.map((s) => [s.sucursalId, s.provincia])
  );
  const totals = new Map<string, ProvinceTotal>();
  for (const c of byCanal(cells, canal)) {
    const provincia = provinciaDe.get(c.sucursalId);
    if (provincia === undefined) continue;
    const current = totals.get(provincia) ?? {
      provincia,
      transacciones: 0,
      monto: 0,
    };
    current.transacciones += c.transacciones;
    current.monto += c.monto;
    totals.set(provincia, current);
  }
  return [...totals.values()].sort((a, b) => b.monto - a.monto);
}

/** Meses 'YYYY-MM' entre dos fechas ISO (inclusive). */
export function monthsBetween(minDate: string, maxDate: string): string[] {
  const months: string[] = [];
  let year = Number(minDate.slice(0, 4));
  let month = Number(minDate.slice(5, 7));
  const lastYear = Number(maxDate.slice(0, 4));
  const lastMonth = Number(maxDate.slice(5, 7));
  while (year < lastYear || (year === lastYear && month <= lastMonth)) {
    months.push(`${year}-${String(month).padStart(2, '0')}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return months;
}

/** Primer día del mes y del mes siguiente, como fechas UTC. */
export function monthBounds(mes: string): { start: Date; end: Date } {
  const year = Number(mes.slice(0, 4));
  const month = Number(mes.slice(5, 7));
  return {
    start: new Date(Date.UTC(year, month - 1, 1)),
    end: new Date(Date.UTC(year, month, 1)),
  };
}

export interface Reconciliation {
  /** Filas del resumen que no coinciden con lo calculado desde el hecho. */
  differences: string[];
  checked: number;
}

/**
 * Compara el cálculo por mes y canal con `transacciones.resumen_mes_canal`.
 * Los montos se comparan al centavo.
 */
export function reconcileWithSummary(
  cells: readonly MonthCell[],
  summary: readonly SummaryRow[]
): Reconciliation {
  const calculated = new Map<
    string,
    { transacciones: number; creditos: number; debitos: number }
  >();
  for (const c of cells) {
    const key = `${c.mes}|${c.canal}`;
    const current = calculated.get(key) ?? {
      transacciones: 0,
      creditos: 0,
      debitos: 0,
    };
    current.transacciones += c.transacciones;
    if (c.direccion === CREDITO) current.creditos += c.monto;
    else current.debitos += c.monto;
    calculated.set(key, current);
  }

  const differences: string[] = [];
  for (const row of summary) {
    const key = `${row.mes}|${row.canal}`;
    const own = calculated.get(key);
    const matches =
      own !== undefined &&
      own.transacciones === row.transacciones &&
      Math.abs(own.creditos - row.montoCreditos) < 0.01 &&
      Math.abs(own.debitos - row.montoDebitos) < 0.01;
    if (!matches) differences.push(key);
    calculated.delete(key);
  }
  for (const key of calculated.keys()) differences.push(key);

  return { differences, checked: summary.length };
}
