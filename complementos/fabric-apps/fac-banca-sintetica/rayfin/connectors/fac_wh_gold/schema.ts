import type { GraphQLBackedConnector } from '@microsoft/rayfin-connector-fabric-graphql';
import type { ConnectorConfig } from '@microsoft/rayfin-connectors';

import { DimCliente } from './DimCliente.js';
import { DimCuenta } from './DimCuenta.js';
import { DimSucursal } from './DimSucursal.js';
import { FactTransaccion } from './FactTransaccion.js';
import { ResumenMesCanal } from './ResumenMesCanal.js';

export { DimCliente } from './DimCliente.js';
export { DimCuenta } from './DimCuenta.js';
export { DimSucursal } from './DimSucursal.js';
export { FactTransaccion } from './FactTransaccion.js';
export { ResumenMesCanal } from './ResumenMesCanal.js';

// `as const satisfies` keeps the connector and operations literals that the marker type reads.
export const connectorConfig = {
  connector: 'fabric-warehouse',
  operations: ['read'],
  entities: { DimCliente, DimCuenta, DimSucursal, FactTransaccion, ResumenMesCanal },
} as const satisfies ConnectorConfig;

export type FacWhGoldSchema = GraphQLBackedConnector<
  {
    DimCliente: typeof DimCliente;
    DimCuenta: typeof DimCuenta;
    DimSucursal: typeof DimSucursal;
    FactTransaccion: typeof FactTransaccion;
    ResumenMesCanal: typeof ResumenMesCanal;
  },
  typeof connectorConfig
>;
