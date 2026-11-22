"use client";
import { useState, type FormEvent } from "react";
import { post, money, type Schema } from "../lib/api";
import { useResource } from "../lib/use-resource";
import { Badge, SectionHead, TextLink } from "./ui";
import { ResultView } from "./result-view";
type Measurement = {
  n: number;
  win_fraction: number;
  payoff_ratio: number | null;
  expected_r: number | null;
  random_expected_r: number | null;
};
export function Trade() {
  const [mode, setMode] = useState("position");
  const [market, setMarket] = useState("us");
  const [setup, setSetup] = useState("pullback");
  const [exit, setExit] = useState("A");
  const settings = useResource<Schema["Settings"]>("/settings");
  const validation = useResource<{
    events?: Record<string, Measurement>;
    start: string;
    end: string;
  }>(`/validation/${market}/latest`);
  const measurement = validation.result?.data?.events?.[`${setup}-${exit}`];
  const [result, setResult] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [holdings, setHoldings] = useState<Schema["HoldingInput"][]>([]);
  function addHolding() {
    setHoldings((v) => [
      ...v,
      { symbol: "", sector: "미확인", quantity: 0, price: 100, stop: 95 },
    ]);
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(e.currentTarget);
    const n = (key: string, fallback = 0) => Number(form.get(key) ?? fallback);
    const costs = settings.result?.data.costs;
    try {
      let response;
      if (mode === "execution") {
        const all = await Promise.all(
          (["A", "B", "C"] as const).map(async (choice) => {
            const r = await post<{ summary: Measurement }>("/execution-study", {
              symbol: form.get("symbol"),
              start: form.get("start"),
              setup,
              mode: choice,
              costs,
            });
            return [choice, r.data.summary] as const;
          }),
        );
        response = { data: Object.fromEntries(all) };
      } else if (mode === "expectancy")
        response = await post("/trade-lab/simulate", {
          kind: "loss_streak",
          win_fraction: n("win", 50) / 100,
          payoff_ratio: n("payoff", 2),
          risk_fraction: n("risk", 1) / 100,
          seed: 20261123,
        });
      else if (mode === "stress") {
        const rules = [];
        if (n("sell_quantity") > 0)
          rules.push({
            매매: "매도",
            조건: "이하",
            기준가격: n("sell_price"),
            수량: n("sell_quantity"),
          });
        if (n("buy_quantity") > 0)
          rules.push({
            매매: "매수",
            조건: "이하",
            기준가격: n("buy_price"),
            수량: n("buy_quantity"),
          });
        response = await post("/trade-lab/simulate", {
          kind: "path",
          shares: n("shares", 10),
          average: n("entry", 100),
          cash: n("cash", 10000),
          path: String(form.get("path")).split(",").map(Number),
          rules,
          costs,
        });
      } else if (mode === "ladder")
        response = await post("/trade-lab/plan", {
          kind: "ladder",
          cash: n("cash", 10000),
          prices: String(form.get("prices")).split(",").map(Number),
          weights: String(form.get("weights")).split(",").map(Number),
          reserve_pct: n("reserve", 0),
          costs,
        });
      else
        response = await post("/trade-lab/plan", {
          kind: mode,
          account: n("account", 100000),
          cash: n("cash", 100000),
          entry: n("entry", 100),
          stop: n("stop", 95),
          target: n("target", 110),
          risk_pct: n("risk", 1),
          shares: n("shares", 10),
          average: n("average", 100),
          gap_pct: n("gap"),
          sector: String(form.get("sector") ?? "미확인"),
          holdings,
          costs,
          max_position_pct: settings.result?.data.max_position_pct,
        });
      setResult(response.data);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "계산 실패");
    } finally {
      setBusy(false);
    }
  }
  function csv() {
    const raw = result as Record<string, unknown>;
    const rows = Array.isArray(result)
      ? result
      : Array.isArray(raw?.rows)
        ? raw.rows
        : mode === "execution"
          ? Object.entries(raw).map(([mode, value]) => ({
              mode,
              ...(value as object),
            }))
          : [raw];
    if (!rows.length) return;
    const keys = Object.keys(rows[0]);
    const cell = (v: unknown) =>
      `"${String(typeof v === "object" ? JSON.stringify(v) : (v ?? "")).replaceAll('"', '""')}"`;
    const url = URL.createObjectURL(
      new Blob(
        [
          "\ufeff" +
            [
              keys.map(cell).join(","),
              ...rows.map((row) => keys.map((k) => cell(row[k])).join(",")),
            ].join("\n"),
        ],
        { type: "text/csv;charset=utf-8" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "goldnam-trade-lab.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const field = (
    name: string,
    label: string,
    value: string,
    type = "number",
  ) => (
    <label className="form-field" key={name}>
      {label}
      <input
        name={name}
        type={type}
        inputMode={type === "number" ? "decimal" : "text"}
        step="any"
        defaultValue={value}
        required
      />
    </label>
  );
  const account = String(settings.result?.data.account ?? 100000);
  const risk = String(settings.result?.data.risk_pct ?? 1);
  return (
    <>
      <div className="page-head">
        <div>
          <span className="eyebrow">PLAN BEFORE YOU ACT</span>
          <h1>Trade Lab</h1>
          <p>
            비용과 손실 한도를 먼저 계산합니다. 계산 결과는 주문이 아닙니다.
          </p>
        </div>
      </div>
      <section className="panel">
        <div className="tab-bar" role="tablist" aria-label="계산 종류">
          {[
            ["position", "수량·비용"],
            ["ladder", "분할매수"],
            ["target_average", "목표 평단"],
            ["stress", "하락 스트레스"],
            ["expectancy", "기대값·연속손실"],
            ["execution", "청산 A·B·C 검증"],
          ].map(([v, l]) => (
            <button
              key={v}
              role="tab"
              aria-selected={mode === v}
              className={mode === v ? "active" : ""}
              onClick={() => {
                setMode(v);
                setResult(null);
              }}
            >
              {l}
            </button>
          ))}
        </div>
        {(mode === "expectancy" || mode === "execution") && (
          <div className="filters">
            <label className="form-field">
              검증 시장
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value)}
              >
                <option value="us">미국</option>
                <option value="kr">한국</option>
              </select>
            </label>
            <label className="form-field">
              진입 방식
              <select value={setup} onChange={(e) => setSetup(e.target.value)}>
                <option value="pullback">눌림목</option>
                <option value="momentum">모멘텀</option>
              </select>
            </label>
            {mode === "expectancy" && (
              <label className="form-field">
                측정할 청산 가정
                <select value={exit} onChange={(e) => setExit(e.target.value)}>
                  {["A", "B", "C"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        {mode === "expectancy" && (
          <p className="plan-source">
            {measurement
              ? `과거 측정 ${validation.result?.data.start} ~ ${validation.result?.data.end}, N=${measurement.n}. 자동 추천이 아닌 가정 입력의 출처입니다.`
              : "측정 결과 없음 · 아래 기본값 50% / 2R은 편집 가능한 예시 가정입니다."}
          </p>
        )}
        <form
          onSubmit={submit}
          key={`${mode}-${setup}-${exit}-${measurement?.n}-${account}`}
        >
          <div className="form-grid">
            {mode === "execution" ? (
              <>
                {field(
                  "symbol",
                  "종목 티커",
                  market === "us" ? "AAPL" : "005930.KS",
                  "text",
                )}
                {field("start", "검증 시작일", "2020-01-01", "date")}
              </>
            ) : mode === "expectancy" ? (
              <>
                {field(
                  "win",
                  "가정 승률 %",
                  String((measurement?.win_fraction ?? 0.5) * 100),
                )}
                {field(
                  "payoff",
                  "가정 손익비 R",
                  String(measurement?.payoff_ratio ?? 2),
                )}
                {field("risk", "거래당 계좌 위험 %", risk)}
              </>
            ) : mode === "ladder" ? (
              <>
                {field("cash", "사용 가능 현금", account)}
                {field("reserve", "현금 보존 %", "10")}
                {field("prices", "매수가 · 쉼표 구분", "100,95,90", "text")}
                {field("weights", "배분 가중치 · 쉼표 구분", "1,1,2", "text")}
              </>
            ) : mode === "stress" ? (
              <>
                {field("shares", "보유 수량", "10")}
                {field("entry", "평균 매수가", "100")}
                {field("cash", "현금", "10000")}
                {field(
                  "path",
                  "가격 경로 · 쉼표 구분",
                  "100,95,90,80,100",
                  "text",
                )}
                {field("sell_price", "이 가격 이하에서 매도", "90")}
                {field("sell_quantity", "매도 수량 · 0은 규칙 없음", "0")}
                {field("buy_price", "이 가격 이하에서 매수", "80")}
                {field("buy_quantity", "매수 수량 · 0은 규칙 없음", "0")}
              </>
            ) : mode === "target_average" ? (
              <>
                {field("shares", "보유 수량", "10")}
                {field("average", "현재 평단", "100")}
                {field("entry", "추가 매수가", "80")}
                {field("target", "목표 평단", "90")}
              </>
            ) : (
              <>
                {field("account", "계좌 평가액", account)}
                {field("cash", "사용 가능 현금", account)}
                {field("entry", "진입가", "100")}
                {field("stop", "손절가", "95")}
                {field("target", "목표가", "110")}
                {field("risk", "허용 손실 %", risk)}
                {field("gap", "손절가 아래 추가 갭 %", "0")}
                {field("sector", "신규 종목 업종", "미확인", "text")}
              </>
            )}
          </div>
          {mode === "position" && (
            <details style={{ marginTop: 20 }}>
              <summary>기존 보유 종목 · 포트폴리오 한도 반영</summary>
              <p className="plan-source">
                모든 가격과 계좌는 같은 통화로 입력하세요. 업종명은 같은 표기를
                사용합니다. 미확인은 하나의 업종으로 보수적으로 계산합니다.
              </p>
              {holdings.map((h, i) => (
                <div className="journal-card" key={i}>
                  <div className="form-grid">
                    {(
                      ["symbol", "sector", "quantity", "price", "stop"] as const
                    ).map((k) => (
                      <label className="form-field" key={k}>
                        {
                          {
                            symbol: "종목",
                            sector: "업종",
                            quantity: "수량",
                            price: "현재가",
                            stop: "손절가",
                          }[k]
                        }
                        <input
                          value={h[k]}
                          type={
                            k === "symbol" || k === "sector" ? "text" : "number"
                          }
                          step="any"
                          required
                          onChange={(e) =>
                            setHoldings((all) =>
                              all.map((row, j) =>
                                j === i
                                  ? {
                                      ...row,
                                      [k]:
                                        k === "symbol" || k === "sector"
                                          ? e.target.value
                                          : Number(e.target.value),
                                    }
                                  : row,
                              ),
                            )
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <button
                    className="button small"
                    type="button"
                    onClick={() =>
                      setHoldings((all) => all.filter((_, j) => j !== i))
                    }
                  >
                    보유 행 삭제
                  </button>
                </div>
              ))}
              <button type="button" className="button" onClick={addHolding}>
                보유 종목 추가
              </button>
            </details>
          )}
          <div className="form-actions">
            <button
              className="button primary"
              disabled={busy || settings.loading}
            >
              {busy
                ? "계산 중…"
                : mode === "execution"
                  ? "A·B·C와 무작위 진입 비교"
                  : "계산하기"}
            </button>
            <TextLink href="/settings/">비용 가정 설정</TextLink>
          </div>
        </form>
        <p className="plan-source" style={{ marginTop: 16 }}>
          표시 통화 {settings.result?.data.currency ?? "—"} · 매수 수수료{" "}
          {money((settings.result?.data.costs?.buy_fee ?? 0) * 100)}% · 매도세{" "}
          {money((settings.result?.data.costs?.sell_tax ?? 0) * 100)}%. 환전하지
          않습니다.
        </p>
        {message && <p role="alert">{message}</p>}
      </section>
      {result != null && (
        <section className="panel" style={{ marginTop: 22 }}>
          <SectionHead
            title="계산 결과"
            action={
              <button className="button" onClick={csv}>
                CSV 내보내기
              </button>
            }
          />
          {mode === "execution" ? (
            <div className="grid-three">
              {Object.entries(result as Record<string, Measurement>).map(
                ([mode, v]) => (
                  <article className="journal-card" key={mode}>
                    <Badge>청산 {mode}</Badge>
                    <h3 style={{ marginTop: 16 }}>
                      기대값 {money(v.expected_r)} R
                    </h3>
                    <p>무작위 진입 {money(v.random_expected_r)} R</p>
                    <p>
                      손익비 {money(v.payoff_ratio)} · N={v.n}
                    </p>
                  </article>
                ),
              )}
            </div>
          ) : (
            <ResultView result={result} />
          )}
        </section>
      )}
      <p className="plan-source" style={{ marginTop: 22 }}>
        Decimal 기반 비용 계산. 독립 거래·고정 승률 가정의 연속 손실 실험(100회
        × 10,000, seed 20261123)은 미래 성과 예측이 아닙니다. 청산 검증은 같은
        종목·같은 달의 무작위 진입과 비교합니다.
      </p>
    </>
  );
}
