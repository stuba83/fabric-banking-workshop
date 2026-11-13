import { describe, expect, it } from 'vitest';

import { canalLabel, monthLabel } from './banking-format';
import {
  branchRows,
  computeKpis,
  filterBranchCells,
  monthBounds,
  monthChannelTotals,
  monthsBetween,
  provinceTotals,
  reconcileWithSummary,
  sucursalIdsOf,
  type BranchCell,
  type MonthCell,
  type Sucursal,
} from './banking-metrics';

const sucursales: Sucursal[] = [
  { sucursalId: 'S1', nombre: 'Sucursal 1', provincia: 'Alajuela' },
  { sucursalId: 'S2', nombre: 'Sucursal 2', provincia: 'Cartago' },
];

const branchCells: BranchCell[] = [
  { sucursalId: 'S1', canal: 'WEB', direccion: 'CREDITO', transacciones: 2, monto: 300 },
  { sucursalId: 'S1', canal: 'WEB', direccion: 'DEBITO', transacciones: 3, monto: 200 },
  { sucursalId: 'S1', canal: 'ATM', direccion: 'DEBITO', transacciones: 5, monto: 500 },
  { sucursalId: 'S2', canal: 'WEB', direccion: 'CREDITO', transacciones: 10, monto: 1000 },
];

describe('computeKpis', () => {
  it('calcula transacciones, monto, ticket promedio y neto', () => {
    const kpis = computeKpis(branchCells);
    expect(kpis.transacciones).toBe(20);
    expect(kpis.monto).toBe(2000);
    expect(kpis.ticketPromedio).toBe(100);
    expect(kpis.creditos).toBe(1300);
    expect(kpis.debitos).toBe(700);
    expect(kpis.neto).toBe(600);
  });

  it('identifica el canal principal por transacciones', () => {
    expect(computeKpis(branchCells).canalPrincipal).toEqual({
      canal: 'WEB',
      participacion: 15 / 20,
    });
  });

  it('no divide entre cero cuando no hay datos', () => {
    expect(computeKpis([])).toEqual({
      transacciones: 0,
      monto: 0,
      ticketPromedio: 0,
      creditos: 0,
      debitos: 0,
      neto: 0,
      canalPrincipal: null,
    });
  });
});

describe('filtros por canal y provincia', () => {
  it('filtra por canal', () => {
    const cells = filterBranchCells(branchCells, sucursales, {
      canal: 'ATM',
      provincia: null,
    });
    expect(computeKpis(cells).transacciones).toBe(5);
  });

  it('filtra por provincia y combina ambos filtros', () => {
    const cells = filterBranchCells(branchCells, sucursales, {
      canal: 'WEB',
      provincia: 'Cartago',
    });
    expect(cells).toHaveLength(1);
    expect(computeKpis(cells).monto).toBe(1000);
  });

  it('resuelve las sucursales de una provincia', () => {
    expect(sucursalIdsOf(sucursales, 'Cartago')).toEqual(['S2']);
    expect(sucursalIdsOf(sucursales, null)).toEqual(['S1', 'S2']);
  });
});

describe('tablas y series', () => {
  it('arma una fila por sucursal con su ticket promedio', () => {
    const rows = branchRows(branchCells, sucursales, {
      canal: null,
      provincia: null,
    });
    expect(rows.map((r) => [r.sucursalId, r.transacciones, r.ticketPromedio])).toEqual([
      ['S1', 10, 100],
      ['S2', 10, 100],
    ]);
  });

  it('mantiene una sucursal sin movimientos con ceros', () => {
    const rows = branchRows(branchCells, sucursales, {
      canal: 'ATM',
      provincia: null,
    });
    expect(rows.find((r) => r.sucursalId === 'S2')?.transacciones).toBe(0);
  });

  it('ordena las provincias por monto descendente sin aplicar el filtro de provincia', () => {
    expect(
      provinceTotals(
        [...branchCells, { sucursalId: 'S2', canal: 'ATM', direccion: 'DEBITO', transacciones: 1, monto: 50 }],
        sucursales,
        null
      ).map((p) => p.provincia)
    ).toEqual(['Cartago', 'Alajuela']);
  });

  it('suma por mes y canal en orden cronológico', () => {
    const months: MonthCell[] = [
      { mes: '2026-05', canal: 'WEB', direccion: 'CREDITO', transacciones: 1, monto: 10 },
      { mes: '2026-04', canal: 'WEB', direccion: 'CREDITO', transacciones: 2, monto: 20 },
      { mes: '2026-04', canal: 'WEB', direccion: 'DEBITO', transacciones: 3, monto: 30 },
      { mes: '2026-04', canal: 'ATM', direccion: 'DEBITO', transacciones: 4, monto: 40 },
    ];
    expect(monthChannelTotals(months, null)).toEqual([
      { mes: '2026-04', canal: 'ATM', transacciones: 4, monto: 40 },
      { mes: '2026-04', canal: 'WEB', transacciones: 5, monto: 50 },
      { mes: '2026-05', canal: 'WEB', transacciones: 1, monto: 10 },
    ]);
    expect(monthChannelTotals(months, 'ATM')).toHaveLength(1);
  });
});

describe('meses', () => {
  it('lista los meses entre dos fechas, incluso al cruzar de año', () => {
    expect(monthsBetween('2026-04-01', '2026-09-30')).toEqual([
      '2026-04',
      '2026-05',
      '2026-06',
      '2026-07',
      '2026-08',
      '2026-09',
    ]);
    expect(monthsBetween('2025-11-15', '2026-02-01')).toEqual([
      '2025-11',
      '2025-12',
      '2026-01',
      '2026-02',
    ]);
  });

  it('calcula los límites de un mes (fin exclusivo)', () => {
    const { start, end } = monthBounds('2026-12');
    expect(start.toISOString()).toBe('2026-12-01T00:00:00.000Z');
    expect(end.toISOString()).toBe('2027-01-01T00:00:00.000Z');
  });

  it('etiqueta meses y canales en español', () => {
    expect(monthLabel('2026-04')).toBe('abr 2026');
    expect(canalLabel('BANCA_MOVIL')).toBe('Banca móvil');
    expect(canalLabel('NUEVO')).toBe('NUEVO');
  });
});

describe('conciliación con transacciones.resumen_mes_canal', () => {
  const cells: MonthCell[] = [
    { mes: '2026-04', canal: 'NO_INFORMADO', direccion: 'CREDITO', transacciones: 40, monto: 12214258.03 },
    { mes: '2026-04', canal: 'NO_INFORMADO', direccion: 'DEBITO', transacciones: 15, monto: 3533723.73 },
  ];
  const summary = [
    { mes: '2026-04', canal: 'NO_INFORMADO', transacciones: 55, montoCreditos: 12214258.03, montoDebitos: 3533723.73 },
  ];

  it('no reporta diferencias cuando coinciden', () => {
    expect(reconcileWithSummary(cells, summary)).toEqual({
      differences: [],
      checked: 1,
    });
  });

  it('detecta diferencias de conteo, de monto y filas sin resumen', () => {
    const bad = reconcileWithSummary(
      [{ ...cells[0], transacciones: 41 }, cells[1]],
      summary
    );
    expect(bad.differences).toEqual(['2026-04|NO_INFORMADO']);

    const extra = reconcileWithSummary(
      [...cells, { mes: '2026-05', canal: 'WEB', direccion: 'DEBITO', transacciones: 1, monto: 1 }],
      summary
    );
    expect(extra.differences).toEqual(['2026-05|WEB']);
  });
});

