"use client";
import { useState } from "react";
import Link from "next/link";
import { post, money, type Schema } from "../lib/api";
import { useResource } from "../lib/use-resource";
import {
  Badge,
  EmptyState,
  ErrorState,
  Loading,
  SectionHead,
  STATES,
} from "./ui";
export function HistoryPanel() {
  const r = useResource<
    {
      id: string;
      symbol: string;
      date: string;
      score_version: string;
      scores: Record<string, number | null>;
    }[]
  >("/history");
  const [message, setMessage] = useState("");
  async function upload(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 2_000_000)
        throw new Error(
          "2MB 이하 JSON을 선택하세요. 큰 파일과 SQLite는 README의 로컬 가져오기를 사용하세요.",
        );
      const response = await post<{ imported: number }>(
        "/history/import",
        JSON.parse(await file.text()),
      );
      setMessage(`${response.data.imported}개 v6 기록을 가져왔습니다.`);
      r.reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "가져오기 실패");
    }
  }
  return (
    <section className="panel" style={{ marginTop: 24 }}>
      <SectionHead
        title="기존 v6 분석 기록"
        detail="새 점수와 비교·합산하지 않는 별도 보관함"
        action={
          <label className="button">
            v6 JSON 가져오기
            <input
              className="sr-only"
              type="file"
              accept=".json,application/json"
              onChange={(e) => upload(e.target.files?.[0])}
            />
          </label>
        }
      />
      {message && <p role="status">{message}</p>}
      {r.loading ? (
        <Loading />
      ) : r.error ? (
        <ErrorState message={r.error} reload={r.reload} />
      ) : r.result?.data.length ? (
        r.result.data.map((row) => (
          <article className="journal-card" key={row.id}>
            <header>
              <Link href={`/stock/?symbol=${row.symbol}`}>{row.symbol}</Link>
              <Badge>{row.score_version}</Badge>
            </header>
            <p>
              {row.date} · 기존 Opportunity {money(row.scores.opportunity)}
            </p>
            <p className="plan-source">
              v6 당시 산식의 기록이며 현재 유니버스 순위가 아닙니다.
            </p>
          </article>
        ))
      ) : (
        <EmptyState
          title="가져온 v6 기록이 없습니다"
          detail="기존 앱에서 내보낸 History JSON을 선택하세요. SQLite 원본은 읽기 전용 CLI로 가져올 수 있습니다."
        />
      )}
    </section>
  );
}
export function JournalComparison({ row }: { row: Schema["JournalRecord"] }) {
  const snapshot = row.snapshot as
    | {
        score?: { value: number | null; as_of: string };
        timing?: Schema["SetupSnapshot"];
      }
    | undefined;
  if (!snapshot?.timing)
    return (
      <p className="plan-source">
        거래 전에 확인된 계획 스냅샷이 없어 계획 대비 체결을 비교하지 않습니다.
      </p>
    );
  return (
    <details>
      <summary>계획 대비 실제 체결</summary>
      <p className="plan-source">
        {snapshot.score?.as_of} 종가 기준, 거래일 이전에 알려진 계획만
        사용합니다.
      </p>
      <div className="grid-two">
        {(["pullback", "momentum"] as const).map((key) => {
          const plan = snapshot.timing![key];
          return (
            <div className="journal-card" key={key}>
              <h3>
                {key === "pullback" ? "눌림목" : "모멘텀"} ·{" "}
                {STATES[plan.status] ?? plan.status}
              </h3>
              <dl className="details-list">
                <div>
                  <dt>계획 진입가</dt>
                  <dd>{money(plan.entry_price)}</dd>
                </div>
                <div>
                  <dt>실제 체결가</dt>
                  <dd>{money(row.price)}</dd>
                </div>
                <div>
                  <dt>실제 − 계획</dt>
                  <dd>
                    {plan.entry_price == null
                      ? "—"
                      : money(row.price - plan.entry_price)}
                  </dd>
                </div>
                <div>
                  <dt>계획 손절 / 목표</dt>
                  <dd>
                    {money(plan.stop_loss)} / {money(plan.target1)}
                  </dd>
                </div>
              </dl>
            </div>
          );
        })}
      </div>
    </details>
  );
}

export function AnalysisHistory() {
  const r =
    useResource<
      {
        id: string;
        symbol: string;
        date: string;
        snapshot: Schema["Analysis"];
      }[]
    >("/analysis-history");
  return (
    <section className="panel" style={{ marginTop: 24 }}>
      <SectionHead
        title="최근 분석 기록"
        detail="조회 당시 순위·상태·계획 · 최신 100개"
      />
      {r.result?.data.length ? (
        r.result.data.map((row) => (
          <article className="journal-card" key={row.id}>
            <header>
              <Link href={`/stock/?symbol=${row.symbol}`}>{row.symbol}</Link>
              <Badge>score-v0.1</Badge>
            </header>
            <p>
              {row.date} · 순위 {row.snapshot.score.value ?? "산출 불가"} ·{" "}
              {STATES[row.snapshot.timing?.pullback.status ?? ""] ?? "미확인"}
            </p>
            <p className="plan-source">
              진입 {money(row.snapshot.timing?.pullback.entry_price)} / 손절{" "}
              {money(row.snapshot.timing?.pullback.stop_loss)} / 목표{" "}
              {money(row.snapshot.timing?.pullback.target1)}
            </p>
          </article>
        ))
      ) : (
        <EmptyState
          title="저장된 분석이 없습니다"
          detail="종목 분석을 열면 당시 조회 결과를 기록합니다."
        />
      )}
    </section>
  );
}
