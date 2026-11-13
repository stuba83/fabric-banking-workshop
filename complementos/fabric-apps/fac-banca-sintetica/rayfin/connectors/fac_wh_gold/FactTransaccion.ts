import { entity, date, decimal, text, one, role } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';
import { DimCuenta } from './DimCuenta.js';

@role('authenticated', ['read'])
@entity()
export class FactTransaccion extends Source({ schema: 'transacciones', table: 'fact_transaccion', primaryKey: ['transaccionId'] }) {
  @text({ column: 'transaccion_id', max: 20 }) transaccionId!: string;
  @text({ column: 'cuenta_id', max: 20 }) cuentaId!: string;
  @date({ column: 'fecha_hora' }) fechaHora!: Date;
  @date() fecha!: Date;
  @text({ column: 'tipo_transaccion', max: 30 }) tipoTransaccion!: string;
  @text({ max: 10 }) direccion!: string;
  @text({ max: 20 }) canal!: string;
  @decimal({ precision: 18, scale: 2 }) monto!: number;
  @text({ max: 3 }) moneda!: string;
  @text({ max: 15 }) estado!: string;
  @date({ column: 'fecha_carga' }) fechaCarga!: Date;
  @text({ column: 'lote_id', max: 36 }) loteId!: string;

  @one(() => DimCuenta, { sourceFields: ['cuentaId'], targetFields: ['cuentaId'] })
  dimCuenta!: DimCuenta;
}
