'use client';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
  ScatterChart,
  Scatter,
} from 'recharts';
import { finite, percent, money, decimal, type RecordData } from '@/lib/format';
import { Empty } from './ui';
import { DataTable } from './table';
const colors = ['#64c9c3', '#8c9ad7', '#d7a45e', '#9eacb9'];
export function SeriesChart({
  data,
  series,
  x = 'day',
  unit = 'currency',
  kind = 'line',
  label,
}: {
  data: RecordData[];
  series: { key: string; label: string }[];
  x?: string;
  unit?: 'currency' | 'percent' | 'ratio';
  kind?: 'line' | 'area' | 'bar' | 'scatter';
  label: string;
}) {
  const format = (v: unknown) =>
    unit === 'currency'
      ? money(finite(v), 0)
      : unit === 'percent'
        ? percent(finite(v), 1)
        : decimal(finite(v));
  if (!data.length || !data.some((d) => series.some((s) => finite(d[s.key]) !== null)))
    return (
      <Empty title="No eligible series to chart">
        Values remain unavailable until the selected experiment supplies observations.
      </Empty>
    );
  const axes = (
    <>
      <CartesianGrid stroke="#28323d" vertical={false} strokeDasharray="3 5" />
      <XAxis
        dataKey={x}
        tick={{ fill: '#9ba8b5', fontSize: 11 }}
        tickLine={false}
        axisLine={false}
        minTickGap={35}
      />
      <YAxis
        tick={{ fill: '#9ba8b5', fontSize: 11 }}
        width={65}
        tickLine={false}
        axisLine={false}
        tickFormatter={(v) => format(v)}
        domain={unit === 'currency' ? ['auto', 'auto'] : undefined}
      />
      <Tooltip
        contentStyle={{
          background: '#18222c',
          border: '1px solid #435361',
          borderRadius: 6,
          color: '#f0f4f7',
        }}
        formatter={(v) => format(v)}
      />
      <Legend
        verticalAlign="top"
        align="right"
        wrapperStyle={{ fontSize: 11, paddingBottom: 16 }}
      />
    </>
  );
  const chart =
    kind === 'bar' ? (
      <BarChart data={data} accessibilityLayer>
        {axes}
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            fill={colors[i % 4]}
            radius={[2, 2, 0, 0]}
          />
        ))}
      </BarChart>
    ) : kind === 'scatter' ? (
      <ScatterChart accessibilityLayer>
        <CartesianGrid stroke="#28323d" />
        <XAxis
          type="number"
          dataKey={x}
          name="Estimated volatility"
          tickFormatter={(v) => percent(v)}
        />
        <YAxis
          type="number"
          dataKey={series[0].key}
          name="Estimated return"
          tickFormatter={(v) => percent(v)}
        />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v) => percent(finite(v), 2)} />
        <Scatter name="Solved frontier" data={data} fill={colors[0]} />
      </ScatterChart>
    ) : kind === 'area' ? (
      <AreaChart data={data} accessibilityLayer>
        {axes}
        {series.map((s, i) => (
          <Area
            key={s.key}
            type="linear"
            dataKey={s.key}
            name={s.label}
            stroke={colors[i % 4]}
            fill={colors[i % 4]}
            fillOpacity={0.1}
            isAnimationActive={false}
            connectNulls={false}
          />
        ))}
      </AreaChart>
    ) : (
      <LineChart data={data} accessibilityLayer>
        {axes}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="linear"
            dataKey={s.key}
            name={s.label}
            stroke={colors[i % 4]}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
          />
        ))}
      </LineChart>
    );
  return (
    <figure className="chart-figure">
      <figcaption className="sr-only">
        {label}. {data.length} observations.{' '}
        {unit === 'percent'
          ? 'Fractions formatted as percentages.'
          : unit === 'currency'
            ? 'USD.'
            : 'Dimensionless ratios.'}{' '}
        Missing observations are not joined.
      </figcaption>
      <div className="chart" role="img" aria-label={label}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          {chart}
        </ResponsiveContainer>
      </div>
      <details className="chart-data">
        <summary>View accessible chart data</summary>
        <DataTable
          label={label}
          rows={data}
          columns={[
            { key: x, label: x },
            ...series.map((s) => ({
              key: s.key,
              label: s.label,
              render: (v: unknown) => format(v),
            })),
          ]}
        />
      </details>
    </figure>
  );
}
export function Correlation({ matrix, names }: { matrix: unknown; names: unknown }) {
  if (!Array.isArray(matrix) || !Array.isArray(names) || !names.length)
    return <Empty title="Correlation unavailable" />;
  return (
    <div className="table-scroll">
      <table className="correlation" aria-label="Estimated correlation matrix">
        <thead>
          <tr>
            <th scope="col">Asset</th>
            {names.map((n) => (
              <th key={String(n)} scope="col">
                {String(n)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((r, i) => (
            <tr key={i}>
              <th scope="row">{String(names[i])}</th>
              {Array.isArray(r) &&
                r.map((v, j) => (
                  <td
                    key={j}
                    style={{ background: `rgba(100,201,195,${Math.abs(finite(v) ?? 0) * 0.25})` }}
                  >
                    {decimal(finite(v))}
                  </td>
                ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
