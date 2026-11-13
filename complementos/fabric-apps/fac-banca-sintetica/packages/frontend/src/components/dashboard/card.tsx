import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface CardProps {
  title: string;
  description?: string;
  /** Texto de apoyo mientras se actualizan los datos de la tarjeta. */
  busy?: boolean;
  className?: string;
  children: ReactNode;
}

/** Tarjeta de sección con título; `busy` atenúa el contenido y lo anuncia a lectores de pantalla. */
export function Card({ title, description, busy, className, children }: CardProps) {
  return (
    <section
      aria-label={title}
      aria-busy={busy ? true : undefined}
      className={cn(
        'flex min-w-0 flex-col gap-300 rounded-2xl border border-border bg-card p-400',
        className
      )}
    >
      <div>
        <h2 className="text-400 leading-400 font-semibold text-foreground">{title}</h2>
        {description ? (
          <p className="text-200 text-muted-foreground">{description}</p>
        ) : null}
      </div>
      <div className={cn('min-h-0 flex-1', busy && 'opacity-50 transition-opacity')}>
        {children}
      </div>
    </section>
  );
}

export function EmptyMessage({ children }: { children: ReactNode }) {
  return (
    <p className="flex h-full min-h-40 items-center justify-center text-center text-300 text-muted-foreground">
      {children}
    </p>
  );
}
