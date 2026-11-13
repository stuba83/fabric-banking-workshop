import { entity, date, text, many, role } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';
import { DimCliente } from './DimCliente.js';

@role('authenticated', ['read'])
@entity()
export class DimSucursal extends Source({ schema: 'clientes', table: 'dim_sucursal', primaryKey: ['sucursalId'] }) {
  @text({ column: 'sucursal_id', max: 20 }) sucursalId!: string;
  @text({ column: 'nombre_sintetico', max: 100 }) nombreSintetico!: string;
  @text({ max: 30 }) provincia!: string;
  @date({ column: 'fecha_carga' }) fechaCarga!: Date;
  @text({ column: 'lote_id', max: 36 }) loteId!: string;

  @many(() => DimCliente, { sourceFields: ['sucursalId'], targetFields: ['sucursalId'] })
  dimClientes!: DimCliente[];
}

