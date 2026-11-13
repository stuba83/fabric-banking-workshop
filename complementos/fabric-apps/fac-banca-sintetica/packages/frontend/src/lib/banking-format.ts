const CANAL_LABELS: Record<string, string> = {
  ATM: 'Cajero (ATM)',
  BANCA_MOVIL: 'Banca móvil',
  NO_INFORMADO: 'No informado',
  SUCURSAL: 'Sucursal',
  WEB: 'Web',
};

const MESES = [
  'ene',
  'feb',
  'mar',
  'abr',
  'may',
  'jun',
  'jul',
  'ago',
  'sep',
  'oct',
  'nov',
  'dic',
];

// Mismo separador de miles que usan los gráficos y la tabla (formato '#,0').
const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** Etiqueta legible de un canal; los valores desconocidos se muestran tal cual. */
export function canalLabel(canal: string): string {
  return CANAL_LABELS[canal] ?? canal;
}

/** 'YYYY-MM' → 'abr 2026'. */
export function monthLabel(mes: string): string {
  const [year, month] = mes.split('-');
  const name = MESES[Number(month) - 1];
  return name ? `${name} ${year}` : mes;
}

export function formatInt(value: number): string {
  return integer.format(value);
}

/** Colones completos, p. ej. «₡1 234 567». */
export function formatColones(value: number): string {
  return `₡${integer.format(Math.round(value))}`;
}

/** Colones en millones para tarjetas y ejes, p. ej. «₡19 507 M». */
export function formatMillones(value: number): string {
  return `₡${integer.format(Math.round(value / 1_000_000))} M`;
}

export function formatPercent(fraction: number): string {
  return `${decimal.format(fraction * 100)} %`;
}

