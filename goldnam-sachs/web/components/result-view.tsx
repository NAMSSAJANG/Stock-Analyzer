"use client";
import { money } from "../lib/api";
import { SectionHead } from "./ui";
export function ResultView({ result }: { result: unknown }) {
  if (Array.isArray(result))
    return (
      <div className="stack">
        {result.slice(0, 25).map((row, i) => (
          <div className="journal-card" key={i}>
            <h3>{i + 1} 단계</h3>
            <ResultView result={row} />
          </div>
        ))}
      </div>
    );
  if (result && typeof result === "object") {
    const record = result as Record<string, unknown>;
    return (
      <>
        <dl className="details-list">
          {Object.entries(record)
            .filter(
              ([, v]) =>
                typeof v === "number" || typeof v === "string" || v === null,
            )
            .map(([key, value]) => (
              <div key={key}>
                <dt>
                  {{
                    expected_r: "거래당 기대값 R",
                    break_even_win_fraction: "손익분기 승률 (0~1)",
                    simulations: "시뮬레이션 횟수",
                    trades: "거래 횟수",
                    seed: "난수 시드",
                    note: "해석",
                  }[key] ?? key}
                </dt>
                <dd>
                  {typeof value === "number"
                    ? key === "seed"
                      ? String(value)
                      : money(value)
                    : String(value ?? "—")}
                </dd>
              </div>
            ))}
        </dl>
        {Array.isArray(record.rows) && (
          <>
            <p className="plan-source">최대 25행 미리보기 · 전체는 CSV</p>
            <ResultView result={record.rows} />
          </>
        )}
        {record.caps != null && <ResultView result={record.caps} />}
        {record.journal != null && (
          <>
            <SectionHead title="가정 체결 기록" />
            <ResultView result={record.journal} />
          </>
        )}
        {record.loss_streak && (
          <>
            <SectionHead
              title="최대 연속 손실 분포"
              detail="100회 거래 × 10,000회 가정 실험"
            />
            <ResultView result={record.loss_streak} />
          </>
        )}
        {record.max_drawdown && (
          <>
            <SectionHead title="최대 낙폭 분포" />
            <ResultView result={record.max_drawdown} />
          </>
        )}
      </>
    );
  }
  return <p>{String(result)}</p>;
}
