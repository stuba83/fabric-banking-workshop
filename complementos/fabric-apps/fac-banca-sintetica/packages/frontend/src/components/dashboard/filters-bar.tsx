import { RotateCcw } from 'lucide-react';

import { canalLabel } from '@/lib/banking-format';
import type { Filters, Sucursal } from '@/lib/banking-metrics';

interface FiltersBarProps {
  filters: Filters;
  canales: readonly string[];
  sucursales: readonly Sucursal[];
  onChange: (filters: Filters) => void;
  disabled?: boolean;
}

const selectClass =
  'h-800 min-w-48 rounded-lg border border-input bg-card px-300 text-300 text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-60';

export function FiltersBar({
  filters,
  canales,
  sucursales,
  onChange,
  disabled,
}: FiltersBarProps) {
  const provincias = [...new Set(sucursales.map((s) => s.provincia))].sort(
    (a, b) => a.localeCompare(b, 'es')
  );
  const active = filters.canal !== null || filters.provincia !== null;

  return (
    <form
      aria-label="Filtros"
      className="flex flex-wrap items-end gap-400"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="flex flex-col gap-100">
        <label htmlFor="filtro-canal" className="text-200 font-medium text-muted-foreground">
          Canal
        </label>
        <select
          id="filtro-canal"
          className={selectClass}
          disabled={disabled}
          value={filters.canal ?? ''}
          onChange={(e) => onChange({ ...filters, canal: e.target.value || null })}
        >
          <option value="">Todos los canales</option>
          {canales.map((canal) => (
            <option key={canal} value={canal}>
              {canalLabel(canal)}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-100">
        <label htmlFor="filtro-provincia" className="text-200 font-medium text-muted-foreground">
          Provincia
        </label>
        <select
          id="filtro-provincia"
          className={selectClass}
          disabled={disabled}
          value={filters.provincia ?? ''}
          onChange={(e) =>
            onChange({ ...filters, provincia: e.target.value || null })
          }
        >
          <option value="">Todas las provincias</option>
          {provincias.map((provincia) => (
            <option key={provincia} value={provincia}>
              {provincia}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        disabled={disabled || !active}
        onClick={() => onChange({ canal: null, provincia: null })}
        className="flex h-800 items-center gap-200 rounded-lg border border-border px-300 text-300 text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
      >
        <RotateCcw aria-hidden="true" className="icon-size-200" />
        Limpiar filtros
      </button>
    </form>
  );
}
