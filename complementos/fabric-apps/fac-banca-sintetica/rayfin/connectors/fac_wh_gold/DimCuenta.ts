import { entity, date, decimal, text, one, many, role } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';
import { DimCliente } from './DimCliente.js';
import { FactTransaccion } from './FactTransaccion.js';

@role('authenticated', ['read'])
@entity()
export class DimCuenta extends Source({ schema: 'cuentas', table: 'dim_cuenta', primaryKey: ['cuentaId'] }) {
  @text({ column: 'cuenta_id', max: 20 }) cuentaId!: string;
  @text({ column: 'cliente_id', max: 20 }) clienteId!: string;
  @text({ column: 'producto_id', max: 20 }) productoId!: string;
  @date({ column: 'fecha_apertura' }) fechaApertura!: Date;
  @text({ max: 3 }) moneda!: string;
  @decimal({ column: 'saldo_inicial', precision: 18, scale: 2 }) saldoInicial!: number;
  @date({ column: 'fecha_carga' }) fechaCarga!: Date;
  @text({ column: 'lote_id', max: 36 }) loteId!: string;

  @one(() => DimCliente, { sourceFields: ['clienteId'], targetFields: ['clienteId'] })
  dimCliente!: DimCliente;

  @many(() => FactTransaccion, { sourceFields: ['cuentaId'], targetFields: ['cuentaId'] })
  factTransaccions!: FactTransaccion[];
}
