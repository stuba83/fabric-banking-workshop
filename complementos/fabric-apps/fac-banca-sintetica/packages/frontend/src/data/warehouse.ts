import { getRayfinClient } from '@/lib/rayfin-client';
import {
  monthBounds,
  monthsBetween,
  type BranchCell,
  type MonthCell,
  type Sucursal,
  type SummaryRow,
} from '@/lib/banking-metrics';

export interface BaseData {
  sucursales: Sucursal[];
  /** Una celda (canal, dirección) por sucursal, todo el periodo. */
  branchCells: BranchCell[];
  /** Igual, por mes y para todas las provincias. */
  monthCells: MonthCell[];
  months: string[];
  summary: SummaryRow[];
}

type Warehouse = Awaited<
  ReturnType<typeof getRayfinClient>
>['connectors']['fac_wh_gold'];

// DAB devuelve como máximo 100 grupos por consulta agregada. Cada consulta de
// este archivo agrupa solo por canal y dirección (≤ 10 grupos) y se parte por
// sucursal o por mes para que el resultado nunca se trunque.
const AGGREGATIONS = {
  monto: { sum: 'monto' },
  transacciones: { count: 'monto' },
} as const;

function isoDate(value: unknown): string {
  return (value instanceof Date ? value.toISOString() : String(value)).slice(
    0,
    10
  );
}

async function fetchBranchCells(
  wh: Warehouse,
  sucursalId: string
): Promise<BranchCell[]> {
  const rows = await wh.FactTransaccion.where({
    dimCuenta: { dimCliente: { sucursalId: { eq: sucursalId } } },
  })
    .groupBy(['canal', 'direccion'])
    .aggregate(AGGREGATIONS)
    .execute();
  return rows.map((row) => ({
    sucursalId,
    canal: row.fields.canal,
    direccion: row.fields.direccion,
    transacciones: Number(row.aggregations.transacciones),
    monto: Number(row.aggregations.monto ?? 0),
  }));
}

async function fetchMonthCells(
  wh: Warehouse,
  mes: string,
  sucursalIds: readonly string[] | null
): Promise<MonthCell[]> {
  const { start, end } = monthBounds(mes);
  const rows = await wh.FactTransaccion.where({
    fecha: { gte: start, lt: end },
    ...(sucursalIds
      ? { dimCuenta: { dimCliente: { sucursalId: { in: [...sucursalIds] } } } }
      : {}),
  })
    .groupBy(['canal', 'direccion'])
    .aggregate(AGGREGATIONS)
    .execute();
  return rows.map((row) => ({
    mes,
    canal: row.fields.canal,
    direccion: row.fields.direccion,
    transacciones: Number(row.aggregations.transacciones),
    monto: Number(row.aggregations.monto ?? 0),
  }));
}

/** Serie mensual restringida a un conjunto de sucursales (el filtro de provincia se ejecuta en el Warehouse). */
export async function loadMonthCellsFor(
  months: readonly string[],
  sucursalIds: readonly string[]
): Promise<MonthCell[]> {
  const client = await getRayfinClient();
  const wh = client.connectors.fac_wh_gold;
  const perMonth = await Promise.all(
    months.map((mes) => fetchMonthCells(wh, mes, sucursalIds))
  );
  return perMonth.flat();
}

export async function loadBaseData(): Promise<BaseData> {
  const client = await getRayfinClient();
  const wh = client.connectors.fac_wh_gold;

  const [sucursalRows, first, last, summaryRows] = await Promise.all([
    wh.DimSucursal.select(['sucursalId', 'nombreSintetico', 'provincia'])
      .orderBy({ sucursalId: 'asc' })
      .execute(),
    wh.FactTransaccion.select(['fecha'])
      .orderBy({ fecha: 'asc' })
      .first(1)
      .execute(),
    wh.FactTransaccion.select(['fecha'])
      .orderBy({ fecha: 'desc' })
      .first(1)
      .execute(),
    wh.ResumenMesCanal.select([
      'mes',
      'canal',
      'transacciones',
      'montoCreditos',
      'montoDebitos',
    ])
      .first(1000)
      .execute(),
  ]);

  const sucursales: Sucursal[] = sucursalRows.map((s) => ({
    sucursalId: s.sucursalId,
    nombre: s.nombreSintetico,
    provincia: s.provincia,
  }));
  const months =
    first[0] && last[0]
      ? monthsBetween(isoDate(first[0].fecha), isoDate(last[0].fecha))
      : [];

  const [branchGroups, monthGroups] = await Promise.all([
    Promise.all(sucursales.map((s) => fetchBranchCells(wh, s.sucursalId))),
    Promise.all(months.map((mes) => fetchMonthCells(wh, mes, null))),
  ]);

  return {
    sucursales,
    branchCells: branchGroups.flat(),
    monthCells: monthGroups.flat(),
    months,
    summary: summaryRows.map((r) => ({
      mes: r.mes,
      canal: r.canal,
      transacciones: Number(r.transacciones),
      montoCreditos: Number(r.montoCreditos),
      montoDebitos: Number(r.montoDebitos),
    })),
  };
}

/** Mensaje accionable, sin detalles internos del proveedor. */
export function describeLoadError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (/40[13]|unauthori[sz]ed|forbidden|permission|login/i.test(message)) {
    return 'Tu usuario no tiene permiso para leer el Warehouse o la sesión venció. Verifica tu acceso al área de trabajo y vuelve a intentar.';
  }
  return 'No se pudo consultar el Warehouse. Vuelve a intentar; si persiste, revisa que el elemento y el conector sigan publicados.';
}
