import {
  canalLabel,
  formatColones,
  formatInt,
  formatMillones,
  formatPercent,
} from '@/lib/banking-format';
import type { Kpis } from '@/lib/banking-metrics';

interface KpiCardsProps {
  kpis: Kpis;
}

interface Kpi {
  label: string;
  value: string;
  detail: string;
  title?: string;
}

function buildKpis(kpis: Kpis): Kpi[] {
  return [
    {
      label: 'Transacciones',
      value: formatInt(kpis.transacciones),
      detail: 'Operaciones aplicadas',
    },
    {
      label: 'Monto total',
      value: formatMillones(kpis.monto),
      detail: 'Millones de colones (créditos + débitos)',
      title: formatColones(kpis.monto),
    },
    {
      label: 'Ticket promedio',
      value: formatColones(kpis.ticketPromedio),
      detail: 'Monto por transacción',
    },
    {
      label: 'Canal principal',
      value: kpis.canalPrincipal ? canalLabel(kpis.canalPrincipal.canal) : '—',
      detail: kpis.canalPrincipal
        ? `${formatPercent(kpis.canalPrincipal.participacion)} de las transacciones`
        : 'Sin transacciones',
    },
    {
      label: 'Neto (créditos − débitos)',
      value: `${kpis.neto < 0 ? '−' : ''}${formatMillones(Math.abs(kpis.neto))}`,
      detail: `Entradas ${formatMillones(kpis.creditos)} · salidas ${formatMillones(kpis.debitos)}`,
      title: formatColones(kpis.neto),
    },
  ];
}

export function KpiCards({ kpis }: KpiCardsProps) {
  return (
    <ul
      aria-label="Indicadores clave"
      className="grid grid-cols-1 gap-300 sm:grid-cols-2 lg:grid-cols-5"
    >
      {buildKpis(kpis).map((kpi) => (
        <li
          key={kpi.label}
          title={kpi.title}
          className="flex min-w-0 flex-col gap-100 rounded-2xl border border-border bg-card p-400"
        >
          <span className="text-200 font-medium text-muted-foreground">
            {kpi.label}
          </span>
          <span className="truncate font-numeric text-600 leading-600 font-semibold text-foreground tabular-nums">
            {kpi.value}
          </span>
          <span className="text-200 text-muted-foreground">{kpi.detail}</span>
        </li>
      ))}
    </ul>
  );
}
