import { entity, date, text, one, many, role } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';
import { DimCuenta } from './DimCuenta.js';
import { DimSucursal } from './DimSucursal.js';

@role('authenticated', ['read'])
@entity()
export class DimCliente extends Source({ schema: 'clientes', table: 'dim_cliente', primaryKey: ['clienteId'] }) {
  @text({ column: 'cliente_id', max: 20 }) clienteId!: string;
  @text({ column: 'nombre_sintetico', max: 100 }) nombreSintetico!: string;
  @date({ column: 'fecha_alta' }) fechaAlta!: Date;
  @text({ max: 20 }) segmento!: string;
  @text({ column: 'grupo_edad', max: 10 }) grupoEdad!: string;
  @text({ max: 30 }) provincia!: string;
  @text({ column: 'sucursal_id', max: 20 }) sucursalId!: string;
  @date({ column: 'fecha_carga' }) fechaCarga!: Date;
  @text({ column: 'lote_id', max: 36 }) loteId!: string;

  @one(() => DimSucursal, { sourceFields: ['sucursalId'], targetFields: ['sucursalId'] })
  dimSucursal!: DimSucursal;

  @many(() => DimCuenta, { sourceFields: ['clienteId'], targetFields: ['clienteId'] })
  dimCuentas!: DimCuenta[];
}
