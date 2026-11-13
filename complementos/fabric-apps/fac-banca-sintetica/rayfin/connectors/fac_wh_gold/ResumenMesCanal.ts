import { entity, date, decimal, int, text, role } from '@microsoft/rayfin-core';
import { Source } from '@microsoft/rayfin-connectors';

@role('authenticated', ['read'])
@entity()
export class ResumenMesCanal extends Source({ schema: 'transacciones', table: 'resumen_mes_canal', primaryKey: ['mes', 'canal'] }) {
  @text({ max: 7 }) mes!: string;
  @text({ max: 20 }) canal!: string;
  @int() transacciones!: number;
  @decimal({ column: 'monto_creditos', precision: 18, scale: 2 }) montoCreditos!: number;
  @decimal({ column: 'monto_debitos', precision: 18, scale: 2 }) montoDebitos!: number;
  @date({ column: 'fecha_carga' }) fechaCarga!: Date;
  @text({ column: 'lote_id', max: 36 }) loteId!: string;
}
