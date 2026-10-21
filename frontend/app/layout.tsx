import type { Metadata } from 'next';
import { Suspense } from 'react';
import Providers from '@/components/shell';
import './globals.css';
export const metadata: Metadata = {
  title: 'SentientAlpha — Quantitative Research',
  description:
    'Simulation-only quantitative research, evidence-based investment committee and independent risk governance.',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Suspense fallback={<p className="panel-body">Loading research workspace…</p>}>
            {children}
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
