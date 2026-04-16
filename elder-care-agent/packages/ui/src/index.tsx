import React from "react";

type CardProps = {
  title?: string;
  children: React.ReactNode;
  className?: string;
};

export function Card({ title, children, className = "" }: CardProps) {
  return (
    <section className={`rounded-3xl border border-slate-200 bg-white/90 p-5 shadow-sm ${className}`}>
      {title ? <h2 className="mb-3 text-lg font-semibold text-slate-800">{title}</h2> : null}
      {children}
    </section>
  );
}

type BadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "good" | "warning" | "danger";
};

export function Badge({ children, tone = "neutral" }: BadgeProps) {
  const map = {
    neutral: "bg-slate-100 text-slate-700",
    good: "bg-emerald-100 text-emerald-800",
    warning: "bg-amber-100 text-amber-800",
    danger: "bg-rose-100 text-rose-800"
  } as const;
  return <span className={`inline-flex rounded-full px-3 py-1 text-sm font-medium ${map[tone]}`}>{children}</span>;
}

type SectionTitleProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
};

export function SectionTitle({ eyebrow, title, subtitle }: SectionTitleProps) {
  return (
    <div className="space-y-1">
      {eyebrow ? <p className="text-sm font-semibold uppercase tracking-[0.22em] text-orange-600">{eyebrow}</p> : null}
      <h2 className="text-2xl font-semibold text-slate-900">{title}</h2>
      {subtitle ? <p className="text-sm text-slate-600">{subtitle}</p> : null}
    </div>
  );
}
