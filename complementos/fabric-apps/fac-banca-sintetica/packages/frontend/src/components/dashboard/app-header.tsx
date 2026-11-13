import { Landmark, FlaskConical, Moon, Sun, UserRound } from 'lucide-react';

import { useAuth } from '@/hooks/auth.context';
import { useTheme } from '@/hooks/theme.context';

export function AppHeader() {
  const { session } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const user = session?.user?.email;

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-300 px-400 py-300">
        <div className="flex items-center gap-300">
          <span
            aria-hidden="true"
            className="flex icon-size-600 items-center justify-center rounded-xl bg-primary text-primary-foreground"
          >
            <Landmark className="icon-size-300" />
          </span>
          <div>
            <h1 className="font-heading text-500 leading-500 font-semibold text-foreground">
              Banca sintética
            </h1>
            <p className="text-200 text-muted-foreground">
              Transacciones por canal, mes, provincia y sucursal
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-300">
          <p className="flex items-center gap-200 rounded-full border border-border bg-muted px-300 py-100 text-200 font-medium text-foreground">
            <FlaskConical aria-hidden="true" className="icon-size-200" />
            Datos sintéticos · Taller de Microsoft Fabric
          </p>
          {user ? (
            <p
              className="flex items-center gap-200 text-200 text-muted-foreground"
              title="Usuario conectado con Fabric"
            >
              <UserRound aria-hidden="true" className="icon-size-200" />
              <span className="sr-only">Usuario conectado: </span>
              {user}
            </p>
          ) : null}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isDark ? 'Usar tema claro' : 'Usar tema oscuro'}
            className="flex icon-size-600 items-center justify-center rounded-lg border border-border text-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {isDark ? (
              <Sun aria-hidden="true" className="icon-size-200" />
            ) : (
              <Moon aria-hidden="true" className="icon-size-200" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
