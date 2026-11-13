import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import type { BaseData } from '@/data/warehouse';

// Datos con la forma que devuelve el Warehouse (agregados por canal y dirección).
const base: BaseData = {
  sucursales: [
    { sucursalId: 'S1', nombre: 'Sucursal 1', provincia: 'Alajuela' },
    { sucursalId: 'S2', nombre: 'Sucursal 2', provincia: 'Cartago' },
  ],
  branchCells: [
    { sucursalId: 'S1', canal: 'WEB', direccion: 'CREDITO', transacciones: 2, monto: 3_000_000 },
    { sucursalId: 'S1', canal: 'WEB', direccion: 'DEBITO', transacciones: 3, monto: 2_000_000 },
    { sucursalId: 'S2', canal: 'ATM', direccion: 'DEBITO', transacciones: 5, monto: 5_000_000 },
  ],
  monthCells: [
    { mes: '2026-04', canal: 'WEB', direccion: 'CREDITO', transacciones: 2, monto: 3_000_000 },
    { mes: '2026-04', canal: 'WEB', direccion: 'DEBITO', transacciones: 3, monto: 2_000_000 },
    { mes: '2026-04', canal: 'ATM', direccion: 'DEBITO', transacciones: 5, monto: 5_000_000 },
  ],
  months: ['2026-04'],
  summary: [
    { mes: '2026-04', canal: 'WEB', transacciones: 5, montoCreditos: 3_000_000, montoDebitos: 2_000_000 },
    { mes: '2026-04', canal: 'ATM', transacciones: 5, montoCreditos: 0, montoDebitos: 5_000_000 },
  ],
};

const warehouse = vi.hoisted(() => ({
  loadBaseData: vi.fn(),
  loadMonthCellsFor: vi.fn(),
}));

vi.mock('@/data/warehouse', () => ({
  loadBaseData: warehouse.loadBaseData,
  loadMonthCellsFor: warehouse.loadMonthCellsFor,
  describeLoadError: () => 'No se pudo consultar el Warehouse.',
}));

// Los gráficos usan Vega en un lienzo que jsdom no implementa; aquí solo importa qué se muestra.
vi.mock('@/components/dashboard/charts', () => ({
  MonthlyChart: ({ title }: { title: string }) => <div>{title}</div>,
  ProvinceChart: () => <div>Monto por provincia</div>,
}));
vi.mock('@/components/dashboard/branch-table', () => ({
  BranchTable: ({ rows }: { rows: unknown[] }) => <div>{rows.length} sucursales</div>,
}));

import App from '@/App';
import { AuthContext, type AuthContextValue } from '@/hooks/auth.context';

const auth: AuthContextValue = {
  session: {
    user: { id: 'u1', email: 'persona-de-prueba' },
    isAuthenticated: true,
    isAnonymous: false,
  },
  isAuthenticated: true,
  isLoading: false,
  canSignIn: true,
  signIn: async () => {},
  isSigningIn: false,
  signInError: null,
  config: { kind: 'ready' },
  error: null,
};

function renderApp() {
  return render(
    <AuthContext.Provider value={auth}>
      <App />
    </AuthContext.Provider>
  );
}

describe('App', () => {
  it('muestra el encabezado y el rótulo de datos sintéticos', () => {
    warehouse.loadBaseData.mockReturnValue(new Promise(() => {}));
    renderApp();
    expect(screen.getByRole('heading', { level: 1, name: 'Banca sintética' })).toBeVisible();
    expect(screen.getByText('Datos sintéticos · Taller de Microsoft Fabric')).toBeVisible();
    expect(screen.getByText('persona-de-prueba')).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('Consultando el Warehouse');
  });

  it('muestra los indicadores calculados con los datos del Warehouse', async () => {
    warehouse.loadBaseData.mockResolvedValue(base);
    renderApp();
    const kpis = await screen.findByRole('list', { name: 'Indicadores clave' });
    expect(kpis).toHaveTextContent('Transacciones');
    expect(kpis).toHaveTextContent('10');
    expect(kpis).toHaveTextContent('₡10 M');
    expect(kpis).toHaveTextContent('Ticket promedio');
    expect(screen.getByRole('combobox', { name: 'Canal' })).toBeEnabled();
    expect(screen.getByRole('note')).toHaveTextContent('coinciden');
  });

  it('muestra un error accionable cuando falla la consulta', async () => {
    warehouse.loadBaseData.mockRejectedValue(new Error('boom'));
    renderApp();
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo consultar el Warehouse.');
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});

