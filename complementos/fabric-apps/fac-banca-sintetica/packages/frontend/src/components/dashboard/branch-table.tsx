import { DataGrid, type GridColumnDef } from '@microsoft/fabric-datagrid';
import { useCssTheme } from '@microsoft/fabric-visuals';
import type { DataTable } from '@microsoft/fabric-visuals-core';
import { useMemo } from 'react';

import { Card, EmptyMessage } from '@/components/dashboard/card';
import type { BranchRow } from '@/lib/banking-metrics';

interface BranchTableProps {
  rows: readonly BranchRow[];
  busy?: boolean;
  className?: string;
}

const PAGE_SIZE = 5;

const COLUMNS: GridColumnDef[] = [
  { id: 'sucursal', header: 'Sucursal', width: 190 },
  { id: 'provincia', header: 'Provincia', width: 110 },
  { id: 'transacciones', header: 'Transacciones', width: 130 },
  { id: 'monto', header: 'Monto (M ₡)', width: 120 },
  { id: 'ticket', header: 'Ticket prom. (₡)', width: 140 },
];

/** Tabla ordenable (clic en el encabezado) y paginada por sucursal. */
export function BranchTable({ rows, busy, className }: BranchTableProps) {
  const theme = useCssTheme();

  const data = useMemo<DataTable>(
    () => ({
      columns: [
        { name: 'sucursal', displayName: 'Sucursal' },
        { name: 'provincia', displayName: 'Provincia' },
        { name: 'transacciones', displayName: 'Transacciones', format: '#,0' },
        { name: 'monto', displayName: 'Monto (M ₡)', format: '#,0' },
        { name: 'ticket', displayName: 'Ticket prom. (₡)', format: '#,0' },
      ],
      rows: rows.map((r) => [
        r.sucursal,
        r.provincia,
        r.transacciones,
        Math.round(r.monto / 1_000_000),
        Math.round(r.ticketPromedio),
      ]),
    }),
    [rows]
  );

  return (
    <Card
      title="Detalle por sucursal"
      description="Ordena con un clic en el encabezado; sigue ambos filtros."
      busy={busy}
      className={className}
    >
      {rows.length === 0 ? (
        <EmptyMessage>No hay sucursales para esta combinación de filtros.</EmptyMessage>
      ) : (
        <div className="overflow-auto">
          <DataGrid
            data={data}
            columns={COLUMNS}
            theme={theme}
            capabilities={{
              pagination: PAGE_SIZE,
              disableFiltering: true,
              disableColumnReorder: true,
            }}
            defaultSort={[{ columnId: 'monto', direction: 'desc' }]}
          />
        </div>
      )}
    </Card>
  );
}


