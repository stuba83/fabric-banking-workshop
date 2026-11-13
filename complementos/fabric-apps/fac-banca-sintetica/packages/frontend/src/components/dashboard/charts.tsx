import { VegaVisual, useCssTheme } from '@microsoft/fabric-visuals';
import type { VisualizationSpec } from '@microsoft/fabric-visuals';
import type { DataTable } from '@microsoft/fabric-visuals-core';
import { useMemo } from 'react';

import { Card, EmptyMessage } from '@/components/dashboard/card';
import { canalLabel, monthLabel } from '@/lib/banking-format';
import {
  monthChannelTotals,
  type MonthCell,
  type ProvinceTotal,
} from '@/lib/banking-metrics';
import { useTheme } from '@/hooks/theme.context';

// Un color fijo por canal, con contraste ≥ 3:1 sobre el fondo de cada tema.
const CANAL_COLORS = {
  light: {
    ATM: '#0f6cbd',
    BANCA_MOVIL: '#0b7a75',
    SUCURSAL: '#b45309',
    WEB: '#7c3aed',
    NO_INFORMADO: '#6b7280',
  },
  dark: {
    ATM: '#479ef5',
    BANCA_MOVIL: '#2ec4b6',
    SUCURSAL: '#f5a524',
    WEB: '#b794f6',
    NO_INFORMADO: '#a3a3a3',
  },
} as const;

const ORDEN_CANALES = ['BANCA_MOVIL', 'WEB', 'ATM', 'SUCURSAL', 'NO_INFORMADO'];

function canalScale(isDark: boolean, present: readonly string[]) {
  const palette = isDark ? CANAL_COLORS.dark : CANAL_COLORS.light;
  const domain = ORDEN_CANALES.filter((c) => present.includes(c));
  const extra = present.filter((c) => !ORDEN_CANALES.includes(c));
  return {
    domain: [...domain, ...extra].map(canalLabel),
    range: [
      ...domain.map((c) => palette[c as keyof typeof palette]),
      ...extra.map(() => palette.NO_INFORMADO),
    ],
  };
}

interface MonthlyChartProps {
  cells: readonly MonthCell[];
  canal: string | null;
  metric: 'transacciones' | 'monto';
  title: string;
  description: string;
  busy?: boolean;
}

/** Columnas apiladas por mes; cada color es un canal. */
export function MonthlyChart({
  cells,
  canal,
  metric,
  title,
  description,
  busy,
}: MonthlyChartProps) {
  const theme = useCssTheme();
  const { isDark } = useTheme();

  const { spec, data, summary } = useMemo(() => {
    const totals = monthChannelTotals(cells, canal);
    const meses = [...new Set(totals.map((t) => t.mes))];
    const canales = [...new Set(totals.map((t) => t.canal))];
    const isMonto = metric === 'monto';
    const table: DataTable = {
      columns: [
        { name: 'mes', displayName: 'Mes' },
        { name: 'canal', displayName: 'Canal' },
        {
          name: 'valor',
          displayName: isMonto ? 'Monto (millones de ₡)' : 'Transacciones',
          format: '#,0',
        },
      ],
      rows: totals.map((t) => [
        monthLabel(t.mes),
        canalLabel(t.canal),
        isMonto ? Math.round(t.monto / 1_000_000) : t.transacciones,
      ]),
    };
    const chart: VisualizationSpec = {
      $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
      mark: { type: 'bar', tooltip: true },
      encoding: {
        x: {
          field: 'mes',
          type: 'ordinal',
          title: null,
          sort: meses.map(monthLabel),
          axis: { labelAngle: 0 },
        },
        y: { field: 'valor', type: 'quantitative', stack: 'zero' },
        color: {
          field: 'canal',
          type: 'nominal',
          scale: canalScale(isDark, canales),
          legend: { orient: 'bottom', title: null },
        },
      },
    };
    const total = totals.reduce(
      (sum, t) => sum + (isMonto ? t.monto : t.transacciones),
      0
    );
    return {
      spec: chart,
      data: table,
      summary: `${title}: ${meses.length} meses, ${canales.length} canales, total ${
        isMonto ? Math.round(total / 1_000_000) + ' millones de colones' : total + ' transacciones'
      }.`,
    };
  }, [cells, canal, metric, isDark, title]);

  return (
    <Card title={title} description={description} busy={busy}>
      {cells.length === 0 ? (
        <EmptyMessage>{busy ? 'Consultando el Warehouse…' : 'No hay transacciones para esta combinación de filtros.'}</EmptyMessage>
      ) : (
        <div role="img" aria-label={summary}>
          <VegaVisual spec={spec} data={data} theme={theme} style={{ height: 320 }} />
        </div>
      )}
    </Card>
  );
}

interface ProvinceChartProps {
  totals: readonly ProvinceTotal[];
  selected: string | null;
  busy?: boolean;
  className?: string;
}

/** Barras horizontales por provincia; la provincia elegida se resalta y las demás se atenúan. */
export function ProvinceChart({ totals, selected, busy, className }: ProvinceChartProps) {
  const theme = useCssTheme();
  const { isDark } = useTheme();

  const { spec, data, summary } = useMemo(() => {
    const table: DataTable = {
      columns: [
        { name: 'provincia', displayName: 'Provincia' },
        { name: 'monto', displayName: 'Monto (millones de ₡)', format: '#,0' },
        { name: 'transacciones', displayName: 'Transacciones', format: '#,0' },
      ],
      rows: totals.map((t) => [
        t.provincia,
        Math.round(t.monto / 1_000_000),
        t.transacciones,
      ]),
    };
    const chart: VisualizationSpec = {
      $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
      layer: [
        {
          mark: { type: 'bar', tooltip: true },
          encoding: {
            color: { value: isDark ? '#479ef5' : '#0f6cbd' },
            opacity:
              selected === null
                ? { value: 1 }
                : {
                    condition: {
                      test: `datum.provincia === ${JSON.stringify(selected)}`,
                      value: 1,
                    },
                    value: 0.35,
                  },
          },
        },
        {
          mark: { type: 'text', style: 'labelHorizontal' },
          encoding: { text: { field: 'monto', type: 'quantitative' } },
        },
      ],
      encoding: {
        y: {
          field: 'provincia',
          type: 'nominal',
          title: null,
          sort: totals.map((t) => t.provincia),
        },
        x: {
          field: 'monto',
          type: 'quantitative',
          // Deja espacio a la derecha para la etiqueta de la barra más larga.
          scale: { domainMax: Math.ceil(Math.max(0, ...totals.map((t) => t.monto / 1_000_000)) * 1.15) },
        },
      },
    };
    return {
      spec: chart,
      data: table,
      summary: `Monto por provincia: ${totals
        .map((t) => `${t.provincia} ${Math.round(t.monto / 1_000_000)} millones`)
        .join(', ')}.`,
    };
  }, [totals, selected, isDark]);

  return (
    <Card
      title="Monto por provincia"
      description={
        selected
          ? `Se resalta ${selected}; las demás se atenúan.`
          : 'Millones de colones; sigue el filtro de canal.'
      }
      busy={busy}
      className={className}
    >
      {totals.length === 0 ? (
        <EmptyMessage>No hay transacciones para este canal.</EmptyMessage>
      ) : (
        <div role="img" aria-label={summary}>
          <VegaVisual spec={spec} data={data} theme={theme} style={{ height: 320 }} />
        </div>
      )}
    </Card>
  );
}



