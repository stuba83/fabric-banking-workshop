//-----------------------------------------------------------------------
// <copyright company="Microsoft Corporation">
//        Copyright (c) Microsoft Corporation.  All rights reserved.
//        Licensed under the MIT license. See LICENSE file in the project root for full license information.
// </copyright>
//-----------------------------------------------------------------------

import type {
  ConnectorConfig,
  ConnectorsRuntime,
} from '@microsoft/rayfin-connectors';
import {
  connectorConfig as facWhGoldConfig,
  type FacWhGoldSchema,
} from '../../../../rayfin/connectors/fac_wh_gold/schema';

// The key must match `name` in rayfin/rayfin.yml.
export type AppConnectorsSchema = { fac_wh_gold: FacWhGoldSchema };

export const connectorConfigs: Record<string, ConnectorConfig> = {
  fac_wh_gold: facWhGoldConfig,
};

export const connectorRuntimes: ConnectorsRuntime = {};
