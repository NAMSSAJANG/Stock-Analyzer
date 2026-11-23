"use client";
import type { ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Clock3,
  Database,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import type { Schema } from "../lib/api";
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function EvidenceBadge({ value = "미검증" }: { value?: string }) {
  return (
    <Badge tone={value === "근거 있음" ? "positive" : "neutral"}>
      <Clock3 size={12} />
      {value}
    </Badge>
  );
}
export function DataBadge({ source }: { source: Schema["Source"] }) {
  return (
    <Badge
      tone={
        source.status === "stale"
          ? "caution"
          : source.status === "failed"
            ? "negative"
            : "neutral"
      }
    >
      <Database size={11} />
      {source.name} ·{" "}
      {source.status === "failed"
        ? "조회 실패"
        : source.status === "stale"
          ? "오래됨"
          : (source.as_of ?? "현재")}
    </Badge>
  );
}
export function SectionHead({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        {detail && <p>{detail}</p>}
      </div>
      {action}
    </div>
  );
}
export function EmptyState({
  title = "아직 데이터가 없습니다",
  detail,
  action,
}: {
  title?: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Database size={24} />
      <h3>{title}</h3>
      {detail && <p>{detail}</p>}
      {action}
    </div>
  );
}
export function ErrorState({
  message,
  reload,
}: {
  message: string;
  reload: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={20} />
      <div>
        <h3>데이터를 불러오지 못했습니다</h3>
        <p>{message}</p>
      </div>
      <button className="button small" onClick={reload}>
        <RefreshCw size={14} />
        다시 시도
      </button>
    </div>
  );
}
export function Loading({ retrying = false }: { retrying?: boolean }) {
  return (
    <div className="loading" role="status">
      <div className="skeleton" />
      <div className="skeleton short" />
      <p>
        {retrying
          ? "서버를 깨우는 중 · 잠시만 기다려주세요"
          : "데이터를 확인하고 있습니다"}
      </p>
    </div>
  );
}
export function VerdictCard({
  label,
  value,
  detail,
  children,
}: {
  label: string;
  value: string;
  detail: string;
  children?: ReactNode;
}) {
  return (
    <div className="verdict-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
      {children}
    </div>
  );
}
export function FactorBar({
  name,
  score,
}: {
  name: string;
  score: Schema["ScoreModel"];
}) {
  return (
    <div className="factor-row">
      <div>
        <span>{name}</span>
        <strong>
          {score.value ?? "—"}
          <small>/100</small>
        </strong>
      </div>
      <div className="meter">
        <span style={{ width: `${score.value ?? 0}%` }} />
      </div>
      <p>
        지표 커버리지 {Math.round(score.coverage * 100)}%
        {score.value == null ? " · 산출 불가" : ""}
      </p>
    </div>
  );
}
export function TextLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowUpRight size={14} />
    </Link>
  );
}
export function Warnings({ items }: { items: string[] }) {
  return items.length ? (
    <div className="warnings">
      {[...new Set(items)].map((item) => (
        <p key={item}>
          <AlertCircle size={14} />
          {item}
        </p>
      ))}
    </div>
  ) : null;
}
export const FACTORS: Record<string, string> = {
  momentum: "모멘텀",
  trend: "추세 건강도",
  quality: "품질",
  value: "가치",
  growth: "성장",
};
export const STATES: Record<string, string> = {
  READY: "준비",
  DEVELOPING: "형성 중",
  "NOT IN ZONE": "구간 밖",
  "STRUCTURE WARNING": "구조 경고",
  INVALIDATED: "무효",
  CONFIRMED: "돌파 확인",
  "EARLY BREAKOUT": "초기 돌파",
  WATCH: "관찰",
  EXTENDED: "과열",
  "FAILED BREAKOUT": "돌파 실패",
};
export function Footer() {
  return (
    <footer className="footer">
      <span>
        Goldnam Sachs <b>v{process.env.NEXT_PUBLIC_APP_VERSION}</b>
      </span>
      <p>
        정보 제공·학습 목적이며 투자 조언이 아닙니다.
        <br />
        Goldnam Sachs는 개인 프로젝트이며 Goldman Sachs와 관련이 없습니다.
      </p>
    </footer>
  );
}
