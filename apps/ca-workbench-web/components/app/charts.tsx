"use client";
import { useId, type ReactNode } from "react";
import type { Lang } from "../../lib/ownerText";
import { WORKBENCH } from "../../lib/workbenchText";

export type Datum = { label: string; value: number; highlight?: boolean };
type Props = { title: string; unit: string; data: Datum[]; lang?: Lang };
const number = (value: number) => value.toLocaleString("en-IN", { maximumFractionDigits: 1 });
const fill = (datum: Datum) => datum.highlight ? "var(--accent)" : "var(--muted)";

function Chart({ title, unit, data, lang = "en", children }: Props & { children: ReactNode }) {
  const id = useId(), t = WORKBENCH[lang];
  return <figure className="chart-card" lang={lang} aria-labelledby={id}><figcaption id={id}>{title}</figcaption>{children}
    <details className="chart-data"><summary>{t.dataTable}</summary><div className="chart-table" tabIndex={0} role="region" aria-label={title}><table><caption className="sr-only">{title} · {unit}</caption><thead><tr><th scope="col">{t.item}</th><th scope="col">{t.value} ({unit})</th></tr></thead><tbody>{data.map(d => <tr key={d.label}><th scope="row">{d.label}</th><td>{number(d.value)}</td></tr>)}</tbody></table></div></details>
  </figure>;
}

export function BarChart(props: Props) {
  const { title, unit, data } = props, max = Math.max(1, ...data.map(d => d.value)), width = Math.max(420, data.length * 120), step = (width - 88) / Math.max(1, data.length);
  return <Chart {...props}><div className="chart-scroll"><svg viewBox={`0 0 ${width} 290`} role="img" aria-label={`${title} · ${unit}`}><title>{title}</title>
    <text x="52" y="18">{unit}</text>{[0, .5, 1].map(tick => <g key={tick}><line className="chart-grid" x1="52" x2={width - 20} y1={220 - tick * 170} y2={220 - tick * 170} /><text x="44" y={224 - tick * 170} textAnchor="end">{number(max * tick)}</text></g>)}
    {data.map((d, i) => { const x = 52 + i * step + step * .2, height = d.value / max * 170; return <g key={d.label}><rect x={x} y={220 - height} width={step * .6} height={height} fill={fill(d)} rx="3" /><text x={x + step * .3} y={210 - height} textAnchor="middle">{number(d.value)}</text><text x={x + step * .3} y="244" textAnchor="middle">{d.label}</text></g>; })}
  </svg></div></Chart>;
}

export function HorizontalBarChart(props: Props) {
  const { title, unit, data } = props, max = Math.max(1, ...data.map(d => d.value)), height = Math.max(140, data.length * 62 + 70);
  return <Chart {...props}><div className="chart-scroll"><svg viewBox={`0 0 620 ${height}`} role="img" aria-label={`${title} · ${unit}`}><title>{title}</title>
    {data.map((d, i) => <g key={d.label}><text x="12" y={25 + i * 62}>{d.label}</text><rect x="12" y={34 + i * 62} width={d.value / max * 550} height="14" rx="3" fill={fill(d)} /><text x={22 + d.value / max * 550} y={47 + i * 62}>{number(d.value)}</text></g>)}
    <line className="chart-grid" x1="12" x2="562" y1={height - 50} y2={height - 50} />{[0, .5, 1].map(tick => <text key={tick} x={12 + tick * 550} y={height - 31} textAnchor={tick === 0 ? "start" : "middle"}>{number(max * tick)}</text>)}<text x="12" y={height - 7}>{unit}</text>
  </svg></div></Chart>;
}

export function Sparkline(props: Props & { xLabel: string }) {
  const { title, unit, xLabel, data } = props, max = Math.max(1, ...data.map(d => d.value)), x = (i: number) => 52 + i / Math.max(1, data.length - 1) * 480, y = (value: number) => 190 - value / max * 140;
  return <Chart {...props}><div className="chart-scroll"><svg viewBox="0 0 580 270" role="img" aria-label={`${title} · ${xLabel} · ${unit}`}><title>{title}</title>
    <text x="52" y="18">{unit}</text>{[0, .5, 1].map(tick => <g key={tick}><line className="chart-grid" x1="52" x2="532" y1={y(max * tick)} y2={y(max * tick)} /><text x="44" y={y(max * tick) + 4} textAnchor="end">{number(max * tick)}</text></g>)}
    <polyline points={data.map((d, i) => `${x(i)},${y(d.value)}`).join(" ")} fill="none" stroke="var(--muted)" strokeWidth="2.5" />{data.map((d, i) => <g key={d.label}><circle cx={x(i)} cy={y(d.value)} r={d.highlight ? 5 : 3} fill={fill(d)} />{(i === 0 || i === data.length - 1 || i % 4 === 0 || d.highlight) && <text x={x(i)} y={d.highlight ? 229 : 213} textAnchor="middle">{d.label}</text>}{d.highlight && <text x={x(i)} y={y(d.value) - 12} textAnchor="middle">{number(d.value)}×</text>}</g>)}<text x="292" y="258" textAnchor="middle">{xLabel}</text>
  </svg></div></Chart>;
}

export function StackedBarChart(props: Props) {
  const { title, unit, data } = props, total = data.reduce((sum, d) => sum + d.value, 0), scale = 480 / Math.max(1, total);
  let offset = 0;
  return <Chart {...props}><div className="chart-scroll"><svg viewBox={`0 0 580 ${150 + data.length * 28}`} role="img" aria-label={`${title} · ${unit}`}><title>{title}</title>
    <text x="52" y="22">{unit}</text>{data.map(d => { const start = offset; offset += d.value; return <rect key={d.label} x={52 + start * scale} y="45" width={d.value * scale} height="34" fill={fill(d)} stroke="var(--surface)" strokeWidth="2" />; })}
    {[0, .5, 1].map(tick => <text key={tick} x={52 + tick * 480} y="102" textAnchor="middle">{number(total * tick)}</text>)}
    {data.map((d, i) => <g key={d.label}><rect x="52" y={126 + i * 28} width="12" height="12" fill={fill(d)} /><text x="74" y={137 + i * 28}>{d.label}: {number(d.value)}</text></g>)}
  </svg></div></Chart>;
}
