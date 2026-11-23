"use client";
import { useState, type FormEvent } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import Image from "next/image";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ArrowUpRight,
  Check,
  ChevronRight,
  FlaskConical,
  Plus,
  Search as SearchIcon,
  Trash2,
} from "lucide-react";
import {
  Bar,
  BarChart,
  LineChart,
  Line,
  ReferenceLine,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, money, pct, post, type Schema } from "../lib/api";
import { useResource } from "../lib/use-resource";
import { applyTheme } from "./shell";
import {
  Badge,
  DataBadge,
  EmptyState,
  ErrorState,
  EvidenceBadge,
  FactorBar,
  FACTORS,
  Loading,
  SectionHead,
  STATES,
  TextLink,
  VerdictCard,
  Warnings,
} from "./ui";
import brands from "../theme/brands.json";
import { HistoryPanel, JournalComparison, AnalysisHistory } from "./history";
const ZoneChart = dynamic(() => import("./zone-chart"), {
  ssr: false,
  loading: () => <Loading />,
});
type ScoreRow = Schema["ScoreRow"];
type MarketData = {
  regime: Schema["MarketRegimeSnapshot"] | null;
  source: Schema["Source"];
  fx: { data: number | null; status: string; as_of: string };
  as_of: string;
};
function PageHead({
  overline,
  title,
  detail,
  action,
}: {
  overline: string;
  title: string;
  detail: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <span className="eyebrow">{overline}</span>
        <h1>{title}</h1>
        <p>{detail}</p>
      </div>
      {action}
    </div>
  );
}
function ResourceError({
  resource,
}: {
  resource: {
    loading: boolean;
    retrying: boolean;
    error: string;
    reload: () => void;
  };
}) {
  return resource.loading ? (
    <Loading retrying={resource.retrying} />
  ) : resource.error ? (
    <ErrorState message={resource.error} reload={resource.reload} />
  ) : null;
}
function Ticker({ row }: { row: { symbol: string; name?: string | null } }) {
  return (
    <>
      <span className="ticker-mark">
        {row.symbol.replace(/\..*/, "").slice(0, 4)}
      </span>
      <span className="ticker-text">
        <strong>{row.symbol}</strong>
        <small>{row.name ?? "종목 분석"}</small>
      </span>
    </>
  );
}
function MarketCard({ market }: { market: "us" | "kr" }) {
  const r = useResource<MarketData>(`/market/${market}/regime`);
  const regime = r.result?.data.regime;
  return (
    <div className="panel market-card">
      <div className="market-title">
        <span className="market-flag">{market.toUpperCase()}</span>
        <div>
          <h3>{market === "us" ? "미국 시장" : "한국 시장"}</h3>
          <small className="muted">
            {market === "us" ? "S&P 500 기준" : "KOSPI 기준"}
          </small>
        </div>
        <Link
          href="/market/"
          className="row-arrow"
          aria-label={`${market === "us" ? "미국" : "한국"} 시장 상세`}
        >
          <ArrowUpRight size={17} />
        </Link>
      </div>
      {r.loading ? (
        <Loading />
      ) : (
        <>
          <div className="market-state">{regime?.label ?? "미확인"}</div>
          <div className="market-sub">
            <span>
              {r.result?.data.as_of ?? "지수 데이터 확인 필요"}
              <br />
              포지션 크기에만 반영
            </span>
            <div className="mini-bars" aria-hidden="true">
              {Object.values(regime?.components ?? {}).map((v, i) => (
                <span
                  key={i}
                  style={{ height: `${Math.max(4, (v / 100) * 30)}px` }}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
export function Home() {
  const watch = useResource<
    {
      symbol: string;
      score: number | null;
      score_change: number | null;
      timing: string | null;
      previous_timing: string | null;
    }[]
  >("/watchlist/status");
  const scores = useResource<Schema["Screener"]>(
    "/universe/us/scores?page_size=5&actionable=true",
  );
  return (
    <>
      <PageHead
        overline="RESEARCH OVERVIEW"
        title="오늘의 리서치"
        detail="순위와 진입 타이밍을 구분하고, 근거를 함께 확인하세요."
        action={
          <Link href="/search/" className="button">
            <Plus size={15} />
            종목 살펴보기
          </Link>
        }
      />
      <div className="grid-two">
        <MarketCard market="us" />
        <MarketCard market="kr" />
      </div>
      <div className="home-split">
        <section className="panel">
          <SectionHead
            title="관심종목"
            detail="나의 관찰 목록"
            action={<TextLink href="/search/">종목 추가</TextLink>}
          />
          <ResourceError resource={watch} />
          {watch.result?.data.length ? (
            <div>
              {watch.result.data.map((row) => (
                <Link
                  className="search-result"
                  key={row.symbol}
                  href={`/stock/?symbol=${encodeURIComponent(row.symbol)}`}
                >
                  <Ticker row={row} />
                  <span className="watch-meta">
                    {row.score ?? "—"}{" "}
                    {row.score_change != null
                      ? `(${row.score_change > 0 ? "+" : ""}${row.score_change})`
                      : ""}
                    <small>{STATES[row.timing ?? ""] ?? "미확인"}</small>
                  </span>
                  <span className="row-arrow">
                    <ChevronRight size={17} />
                  </span>
                </Link>
              ))}
            </div>
          ) : !watch.loading && !watch.error ? (
            <EmptyState
              title="관찰할 종목을 추가하세요"
              detail="종목 분석 화면에서 관심종목에 담을 수 있습니다."
              action={<TextLink href="/search/">첫 종목 찾기</TextLink>}
            />
          ) : null}
        </section>
        <section className="panel">
          <SectionHead
            title="오늘 조건을 충족한 종목"
            detail="최근 배치 기준 · 미국"
            action={<TextLink href="/screener/">전체 보기</TextLink>}
          />
          {scores.result?.data.items.length ? (
            <div>
              {scores.result.data.items.map((row) => (
                <Link
                  className="search-result"
                  key={row.symbol}
                  href={`/stock/?symbol=${row.symbol}`}
                >
                  <Ticker row={row} />
                  <span className="row-arrow score-number">
                    {row.score.value ?? "—"}
                  </span>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              title="조건을 충족한 배치 종목이 없습니다"
              detail="눌림목 준비 또는 모멘텀 돌파 확인 상태만 표시합니다. 배치 미실행 시에도 비어 있습니다."
            />
          )}
        </section>
      </div>
      <div className="research-note" style={{ marginTop: 24 }}>
        <FlaskConical size={23} />
        <div>
          <strong>점수와 근거는 다른 이야기입니다.</strong>높은 순위가 미래
          수익을 보장하지 않습니다. 과거 검증, 데이터 커버리지, 비용 가정을 함께
          확인하세요. <TextLink href="/evidence/">검증 결과 확인</TextLink>
        </div>
      </div>
    </>
  );
}
export function SearchPage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const r = useResource<Schema["SearchHit"][]>(
    submitted ? `/search?q=${encodeURIComponent(submitted)}` : null,
  );
  function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(query.trim());
  }
  return (
    <>
      <PageHead
        overline="FIND YOUR NEXT QUESTION"
        title="종목 검색"
        detail="티커, 종목 코드 또는 한글 이름으로 검색하세요."
      />
      <form className="search-box" onSubmit={submit}>
        <SearchIcon size={21} />
        <input
          autoFocus
          aria-label="종목 검색"
          placeholder="애플, AAPL, 삼성전자…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          maxLength={60}
        />
        <button className="button primary" disabled={!query.trim()}>
          검색
        </button>
      </form>
      <div className="search-results">
        {submitted ? (
          <>
            <SectionHead
              title={`‘${submitted}’ 검색 결과`}
              detail="미국 · 한국 주식"
            />
            <ResourceError resource={r} />
            {r.result?.data.map((row) => (
              <Link
                className="search-result"
                key={row.symbol}
                href={`/stock/?symbol=${encodeURIComponent(row.symbol)}`}
              >
                <Ticker row={row} />
                <Badge>{row.market.toUpperCase()}</Badge>
                <ChevronRight size={17} className="row-arrow" />
              </Link>
            ))}
            {r.result && !r.result.data.length && (
              <EmptyState
                title="검색 결과가 없습니다"
                detail="티커 또는 6자리 종목 코드로 다시 검색해 보세요."
              />
            )}
          </>
        ) : (
          <div className="research-note">
            <SearchIcon size={22} />
            <div>
              <strong>질문에서 시작하는 리서치</strong>예: AAPL · MSFT ·
              005930.KS
              <br />
              검색 결과에서 종목을 열면 순위, 타이밍, 리스크를 따로 확인할 수
              있습니다.
            </div>
          </div>
        )}
      </div>
    </>
  );
}
function SizingCalculator({
  plan,
  risk,
}: {
  plan: Schema["SetupScore"];
  risk: Schema["RiskState"] | null | undefined;
}) {
  const [account, setAccount] = useState("100000");
  const [riskPct, setRiskPct] = useState("1");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  async function calculate(e: FormEvent) {
    e.preventDefault();
    try {
      const r = await post<Record<string, unknown>>("/trade-lab/plan", {
        account: Number(account),
        cash: Number(account),
        entry: plan.entry_price,
        stop: plan.stop_loss,
        target: plan.target1,
        risk_pct: Number(riskPct),
        multiplier: risk?.position_size_multiplier ?? 0,
      });
      setResult(r.data);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "계산 실패");
    }
  }
  return (
    <form onSubmit={calculate}>
      <div className="form-grid">
        <label className="form-field">
          계좌 평가액 · 종목 통화
          <input
            inputMode="decimal"
            type="number"
            min="1"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            required
          />
        </label>
        <label className="form-field">
          거래당 허용 손실 %
          <input
            inputMode="decimal"
            type="number"
            step="0.1"
            min="0"
            max="6"
            value={riskPct}
            onChange={(e) => setRiskPct(e.target.value)}
            required
          />
        </label>
      </div>
      <button
        className="button full"
        style={{ marginTop: 14 }}
        disabled={!plan.entry_price || !plan.stop_loss || !plan.target1}
      >
        허용 수량 계산
      </button>
      {result && (
        <>
          <div className="plan-result">
            <span className="muted">한도 내 수량</span>
            <strong>
              {String(result["수량"])}
              <small> 주</small>
            </strong>
          </div>
          <p className="plan-source" style={{ marginTop: 9 }}>
            비용·현금·종목 비중·포트폴리오 히트 반영. 갭 발생 시 예상 손실을
            초과할 수 있습니다.
          </p>
        </>
      )}
      {error && (
        <p role="alert" className="caution">
          {error}
        </p>
      )}
    </form>
  );
}
export function Stock() {
  const params = useSearchParams();
  const symbol = params.get("symbol") ?? "AAPL";
  const r = useResource<Schema["Analysis"]>(
    `/stocks/${encodeURIComponent(symbol)}/analysis`,
  );
  const [range, setRange] = useState("1y");
  const p = useResource<Schema["PriceData"]>(
    `/stocks/${encodeURIComponent(symbol)}/prices?range=${range}`,
  );
  const [setup, setSetup] = useState<"pullback" | "momentum">("pullback");
  const [tab, setTab] = useState("factors");
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState("");
  const d = r.result?.data;
  const plan = d?.timing?.[setup];
  async function save() {
    try {
      await post("/watchlist", { symbol });
      setSaved(true);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "저장 실패");
    }
  }
  if (!d)
    return (
      <>
        <PageHead
          overline="STOCK RESEARCH"
          title={symbol}
          detail="시세와 데이터 출처를 확인하고 있습니다."
        />
        <ResourceError resource={r} />
      </>
    );
  return (
    <>
      <div className="stock-header">
        <div className="stock-identity">
          <span className="ticker-mark">{symbol.slice(0, 4)}</span>
          <div>
            <h1>{d.name ?? symbol}</h1>
            <p>
              {symbol} · {d.market?.toUpperCase()}{" "}
              <span className="muted"> / 주식</span>
            </p>
          </div>
        </div>
        <div className="quote">
          <strong>
            {d.market === "kr" ? "₩" : "$"}
            {money(d.last_price, d.market === "kr" ? "KRW" : "USD")}
          </strong>
          <span className={(d.change_pct ?? 0) >= 0 ? "positive" : "negative"}>
            {pct(d.change_pct)}
          </span>
        </div>
      </div>
      <div className="badge-row">
        {r.result?.meta.sources?.slice(0, 3).map((s, i) => (
          <DataBadge key={i} source={s} />
        ))}
        <button
          className="button small"
          onClick={save}
          style={{ marginLeft: "auto" }}
        >
          {saved ? <Check size={13} /> : <Plus size={13} />}관심종목
          {saved ? " 추가됨" : ""}
        </button>
      </div>
      {notice && <p role="alert">{notice}</p>}
      <div className="verdict-strip">
        <VerdictCard
          label="01 / 종합 순위"
          value={d.score.value == null ? "산출 불가" : `${d.score.value} / 100`}
          detail={d.grade ?? "유니버스 상대 순위"}
        >
          {d.score.badges?.slice(0, 1).map((b) => (
            <Badge key={b}>{b}</Badge>
          ))}
        </VerdictCard>
        <VerdictCard
          label="02 / 진입 타이밍"
          value={
            d.timing
              ? (STATES[d.timing.pullback.status] ?? d.timing.pullback.status)
              : "미확인"
          }
          detail={
            d.timing
              ? "눌림목 기준 · 순위와 별도 판단"
              : "충분한 시세·지수 데이터 필요"
          }
        />
        <VerdictCard
          label="03 / 리스크"
          value={
            d.risk?.level === "LOW"
              ? "낮음"
              : d.risk?.level === "MODERATE"
                ? "보통"
                : d.risk?.level === "HIGH"
                  ? "높음"
                  : d.risk?.level === "EXTREME"
                    ? "매우 높음"
                    : "미확인"
          }
          detail={d.risk?.earnings ?? "리스크 데이터 없음"}
        />
        <VerdictCard
          label="04 / 과거 근거"
          value={d.score.evidence ?? "미검증"}
          detail="과거 성과는 미래 성과를 보장하지 않음"
        />
      </div>
      <div className="stock-grid">
        <section className="panel stock-chart">
          <SectionHead
            title="가격과 구조"
            action={
              <div className="range-tabs">
                {["3m", "1y", "5y"].map((value) => (
                  <button
                    key={value}
                    className={range === value ? "active" : ""}
                    onClick={() => setRange(value)}
                  >
                    {value === "3m" ? "3개월" : value === "1y" ? "1년" : "5년"}
                  </button>
                ))}
              </div>
            }
          />
          <ResourceError resource={p} />
          {p.result && (
            <ZoneChart bars={p.result.data.bars} zones={d.zones} plan={plan} />
          )}
          <p className="plan-source" style={{ marginTop: 15 }}>
            수정 일봉 · 손가락으로 확대·이동 · 구조가 없는 목표는 ATR 기준
          </p>
        </section>
        <section className="panel stock-plan">
          <SectionHead title="진입 계획" />
          <div className="segmented" style={{ width: "100%" }}>
            <button
              style={{ flex: 1 }}
              className={setup === "pullback" ? "active" : ""}
              onClick={() => setSetup("pullback")}
            >
              눌림목
            </button>
            <button
              style={{ flex: 1 }}
              className={setup === "momentum" ? "active" : ""}
              onClick={() => setSetup("momentum")}
            >
              모멘텀
            </button>
          </div>
          {plan ? (
            <>
              <div className="badge-row" style={{ marginTop: 15 }}>
                <Badge>{STATES[plan.status] ?? plan.status}</Badge>
                <Badge>{d.timing?.preferred ?? "비교 근거 없음"}</Badge>
              </div>
              <div className="plan-prices">
                {[
                  ["진입", plan.entry_price],
                  ["손절", plan.stop_loss],
                  ["목표 1", plan.target1],
                  ["목표 / 위험", plan.risk_reward1],
                ].map(([label, value]) => (
                  <div key={String(label)}>
                    <span>{label}</span>
                    <b>
                      {money(value as number | null)}
                      {label === "목표 / 위험" ? " R" : ""}
                    </b>
                  </div>
                ))}
              </div>
              <p className="plan-source">{plan.details["Target source"]}</p>
              <hr
                style={{
                  border: 0,
                  borderTop: "1px solid var(--border)",
                  margin: "20px 0",
                }}
              />
              <SizingCalculator plan={plan} risk={d.risk} />
            </>
          ) : (
            <EmptyState
              title="계획을 계산할 수 없습니다"
              detail="충분한 가격·지수·구조 데이터가 필요합니다."
            />
          )}
        </section>
        <section className="panel stock-evidence">
          <SectionHead
            title="이 판단의 근거"
            action={<FlaskConical size={17} />}
          />
          <EvidenceBadge value={d.score.evidence} />
          <p
            className="muted"
            style={{ fontSize: 12, lineHeight: 1.9, marginTop: 14 }}
          >
            종합 점수에 대한 검증 근거가 아직 충분하지 않습니다. 가격 팩터만의
            성과를 종합 점수의 성과로 해석하지 마세요.
          </p>
          <TextLink href="/evidence/">검증 범위와 결과 보기</TextLink>
        </section>
        <section className="panel stock-details">
          <div className="tab-bar" role="tablist" aria-label="종목 상세">
            {[
              ["factors", "팩터 분해"],
              ["fundamentals", "펀더멘털"],
              ["technical", "기술 지표"],
              ["options", "옵션"],
              ["canslim", "CAN SLIM"],
            ].map(([value, label]) => (
              <button
                role="tab"
                aria-selected={tab === value}
                key={value}
                className={tab === value ? "active" : ""}
                onClick={() => setTab(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {tab === "factors" ? (
            Object.keys(d.factors ?? {}).length ? (
              Object.entries(d.factors ?? {}).map(([key, value]) => (
                <FactorBar key={key} name={FACTORS[key] ?? key} score={value} />
              ))
            ) : (
              <EmptyState
                title="비교할 유니버스 분포가 없습니다"
                detail="일일 배치 실행 후 팩터 백분위와 커버리지를 확인할 수 있습니다."
              />
            )
          ) : tab === "technical" ? (
            <dl className="details-list">
              {[
                ["RSI", d.technical?.rsi],
                ["ATR %", d.technical?.atr_pct],
                ["거래량 / 20일 평균", d.technical?.volume_ratio],
                ["직전 60일 종가 고점", d.technical?.prior_high60],
                ["200일 지수이평", d.technical?.ema200],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt>{label}</dt>
                  <dd>{money(value as number | undefined)}</dd>
                </div>
              ))}
            </dl>
          ) : tab === "fundamentals" ? (
            <Fundamentals value={d.fundamentals} />
          ) : tab === "options" ? (
            <Options symbol={symbol} market={d.market ?? "us"} />
          ) : (
            <div className="research-note">
              <div>
                <strong>CAN SLIM 참고 뷰 · 별도 점수 없음</strong>실적
                성장·신고가·거래량을 보조적으로 확인합니다. 현재 확인 가능한
                거래량 배율: {money(d.technical?.volume_ratio)}x. 공시 데이터가
                없는 요소는 판정하지 않습니다.
              </div>
            </div>
          )}
        </section>
      </div>
      <Warnings items={r.result?.warnings ?? []} />
    </>
  );
}
function Fundamentals({
  value,
}: {
  value: Record<string, unknown> | null | undefined;
}) {
  const data = value?.data as Record<string, unknown> | null | undefined;
  if (!data)
    return (
      <EmptyState
        title="재무 데이터가 없습니다"
        detail="OpenDART 키와 SEC 연락처 설정 후 확인하세요."
      />
    );
  const labels: Record<string, string> = {
    revenue: "매출",
    net_income: "순이익",
    assets: "자산",
    equity: "자본",
    marketCap: "시가총액",
    totalRevenue: "매출",
    returnOnEquity: "자기자본이익률",
    trailingPE: "PER",
  };
  return (
    <>
      <Badge>
        {value?.current_only
          ? "현재 스냅샷 · 과거 검증 사용 금지"
          : "공시일 기준 PIT"}
      </Badge>
      <dl className="details-list">
        {Object.entries(labels)
          .filter(([key]) => data[key] != null)
          .map(([key, label]) => (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{money(Number(data[key]))}</dd>
            </div>
          ))}
      </dl>
    </>
  );
}
function Options({ symbol, market }: { symbol: string; market: string }) {
  const [requested, setRequested] = useState(false);
  const r = useResource<Schema["Analysis"]>(
    requested
      ? `/stocks/${encodeURIComponent(symbol)}/analysis?include_options=true`
      : null,
  );
  if (market === "kr")
    return <EmptyState title="한국 옵션 데이터는 제공하지 않습니다" />;
  return (
    <>
      {!requested ? (
        <EmptyState
          title="옵션은 별도 렌즈입니다"
          detail="가격·펀더멘털과 구분해서 확인합니다."
          action={
            <button className="button" onClick={() => setRequested(true)}>
              옵션 조회
            </button>
          }
        />
      ) : (
        <>
          <ResourceError resource={r} />
          {r.result?.data.options ? (
            <dl className="details-list">
              {Object.entries(r.result.data.options)
                .filter(
                  ([, v]) => typeof v === "number" || typeof v === "string",
                )
                .map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
            </dl>
          ) : r.result ? (
            <EmptyState title="옵션 소스 응답이 없습니다" />
          ) : null}
        </>
      )}
    </>
  );
}
export function Screener() {
  const [market, setMarket] = useState("us");
  const [sort, setSort] = useState("score");
  const [minimum, setMinimum] = useState("0");
  const [page, setPage] = useState(1);
  const [timing, setTiming] = useState("all");
  const [risk, setRisk] = useState("all");
  const [savedNote, setSavedNote] = useState("");
  const settings = useResource<Schema["Settings"]>("/settings");
  async function saveFilter() {
    if (!settings.result) return;
    try {
      await post("/settings", {
        ...settings.result.data,
        saved_filters: [
          ...(settings.result.data.saved_filters ?? []).slice(-19),
          { market, sort, minimum, timing, risk },
        ],
      });
      settings.reload();
      setSavedNote("필터 저장됨");
    } catch (e) {
      setSavedNote(e instanceof Error ? e.message : "저장 실패");
    }
  }
  const r = useResource<Schema["Screener"]>(
    `/universe/${market}/scores?sort=${sort}&minimum=${minimum}&page=${page}&page_size=20&timing=${timing}&risk=${risk}`,
  );
  const rows = r.result?.data.items ?? [];
  return (
    <>
      <PageHead
        overline="CROSS-SECTIONAL RANKING"
        title="스크리너"
        detail="같은 시장 안에서의 상대 순위입니다. 높은 점수가 진입 신호는 아닙니다."
      />
      <section className="panel">
        <div className="filters">
          <div className="segmented">
            {[
              ["us", "미국"],
              ["kr", "한국"],
            ].map(([v, l]) => (
              <button
                key={v}
                className={market === v ? "active" : ""}
                onClick={() => {
                  setMarket(v);
                  setPage(1);
                }}
              >
                {l}
              </button>
            ))}
          </div>
          <label className="form-field">
            정렬
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
            >
              <option value="score">종합 순위</option>
              {Object.entries(FACTORS).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
              <option value="symbol">티커</option>
              <option value="timing">타이밍</option>
              <option value="risk">리스크 낮은 순</option>
            </select>
          </label>
          <label className="form-field">
            최소 점수
            <select
              value={minimum}
              onChange={(e) => {
                setMinimum(e.target.value);
                setPage(1);
              }}
            >
              <option value="0">전체 · 결측 포함</option>
              <option value="70">70 이상</option>
              <option value="90">90 이상</option>
            </select>
          </label>
          <label className="form-field">
            타이밍
            <select
              value={timing}
              onChange={(e) => {
                setTiming(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">전체</option>
              {["READY", "CONFIRMED", "DEVELOPING", "EXTENDED"].map((v) => (
                <option key={v} value={v}>
                  {STATES[v]}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            리스크
            <select
              value={risk}
              onChange={(e) => {
                setRisk(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">전체</option>
              <option value="LOW">낮음</option>
              <option value="MODERATE">보통</option>
              <option value="HIGH">높음</option>
              <option value="EXTREME">매우 높음</option>
            </select>
          </label>
          <button className="button" onClick={saveFilter}>
            필터 저장
          </button>
          <label className="form-field">
            저장한 필터
            <select
              value=""
              onChange={(e) => {
                const f =
                  settings.result?.data.saved_filters?.[Number(e.target.value)];
                if (f) {
                  setMarket(f.market);
                  setSort(f.sort);
                  setMinimum(f.minimum);
                  setTiming(f.timing);
                  setRisk(f.risk);
                  setPage(1);
                }
              }}
            >
              <option value="">선택</option>
              {settings.result?.data.saved_filters?.map((f, i) => (
                <option key={i} value={i}>
                  {i + 1}. {f.market.toUpperCase()} /{" "}
                  {FACTORS[f.sort] ?? f.sort} / {f.minimum}+
                </option>
              ))}
            </select>
          </label>
          <span role="status">{savedNote}</span>
          <span className="filter-summary">
            {r.result?.data.total ?? 0} 종목 ·{" "}
            {r.result?.meta.as_of ?? "배치 대기"}
          </span>
        </div>
        <ResourceError resource={r} />
        {rows.length ? (
          <>
            <table className="table desktop-table">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>종합</th>
                  {Object.values(FACTORS).map((v) => (
                    <th key={v}>{v}</th>
                  ))}
                  <th>타이밍 / 리스크</th>
                  <th>근거</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.symbol}>
                    <td>
                      <Link href={`/stock/?symbol=${row.symbol}`}>
                        <Ticker row={row} />
                      </Link>
                    </td>
                    <td>
                      <strong>{row.score.value ?? "—"}</strong>
                    </td>
                    {Object.keys(FACTORS).map((k) => (
                      <td key={k}>{row.factors?.[k]?.value ?? "—"}</td>
                    ))}
                    <td>
                      {STATES[row.timing?.pullback.status ?? ""] ?? "미확인"} /{" "}
                      {row.risk?.level ?? "미확인"}
                    </td>
                    <td>
                      <EvidenceBadge value={row.score.evidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mobile-cards">
              {rows.map((row) => (
                <ScreenerCard key={row.symbol} row={row} />
              ))}
            </div>
            <div className="pagination">
              <button
                className="button small"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                이전
              </button>
              <span>
                {page} / {r.result?.data.pages ?? 1}
              </span>
              <button
                className="button small"
                disabled={page >= (r.result?.data.pages ?? 1)}
                onClick={() => setPage(page + 1)}
              >
                다음
              </button>
            </div>
          </>
        ) : !r.loading && !r.error ? (
          <EmptyState
            title="표시할 종목이 없습니다"
            detail="선택한 시장의 배치 데이터 또는 조건을 확인하세요."
          />
        ) : null}
        <Warnings items={r.result?.warnings ?? []} />
      </section>
    </>
  );
}
function ScreenerCard({ row }: { row: ScoreRow }) {
  return (
    <Link className="journal-card" href={`/stock/?symbol=${row.symbol}`}>
      <header>
        <span style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Ticker row={row} />
        </span>
        <strong className="score-number">{row.score.value ?? "—"}</strong>
      </header>
      <div className="badge-row">
        <EvidenceBadge value={row.score.evidence} />
        <Badge>
          {STATES[row.timing?.pullback.status ?? ""] ?? "타이밍 미확인"}
        </Badge>
        <Badge>{row.risk?.level ?? "리스크 미확인"}</Badge>
        {row.score.badges?.slice(0, 1).map((b) => (
          <Badge key={b}>{b}</Badge>
        ))}
      </div>
      <div className="journal-meta">
        {Object.entries(FACTORS).map(([k, l]) => (
          <span key={k}>
            {l}
            <strong>{row.factors?.[k]?.value ?? "—"}</strong>
          </span>
        ))}
      </div>
    </Link>
  );
}
type ValidationReport = {
  scope?: string;
  start?: string;
  end?: string;
  bias?: string;
  composite_evidence?: string;
  prices_available?: number;
  universe_count?: number;
  rankings?: Record<
    string,
    {
      ic_series?: { date: string; ic: number | null }[];
      ic_mean?: number;
      ic_t?: number;
      evidence?: string;
      net_spread?: number;
      quintiles?: Record<string, { mean: number; excess: number }>;
    }
  >;
  events?: Record<
    string,
    {
      n: number;
      expected_r: number | null;
      random_expected_r?: number | null;
      excess_ci95?: [number | null, number | null];
    }
  >;
  default_exit_reason?: string;
};
export function Evidence() {
  const [market, setMarket] = useState("us");
  const r = useResource<ValidationReport | null>(
    `/validation/${market}/latest`,
  );
  const report = r.result?.data;
  const ranking = report?.rankings?.["momentum-63"];
  const chart = Object.entries(ranking?.quintiles ?? {}).map(([q, v]) => ({
    name: `${q}분위`,
    return: v.excess * 100,
  }));
  return (
    <>
      <PageHead
        overline="EVIDENCE, NOT ASSUMPTIONS"
        title="점수의 근거"
        detail="측정한 것과 아직 모르는 것을 구분합니다."
        action={
          <div className="segmented">
            {[
              ["us", "미국"],
              ["kr", "한국"],
            ].map(([v, l]) => (
              <button
                key={v}
                className={market === v ? "active" : ""}
                onClick={() => setMarket(v)}
              >
                {l}
              </button>
            ))}
          </div>
        }
      />
      <ResourceError resource={r} />
      {report ? (
        <div className="stack">
          <div className="research-note">
            <FlaskConical size={24} />
            <div>
              <strong>
                종합 점수: {report.composite_evidence ?? "미검증"}
              </strong>
              {report.scope} · {report.start} ~ {report.end}
              <br />
              {report.bias}
            </div>
          </div>
          <div className="grid-three">
            <div className="panel evidence-metric">
              <span className="eyebrow">가격 모멘텀 / 63일 IC</span>
              <strong>{ranking?.ic_mean?.toFixed(3) ?? "—"}</strong>
              <p>순위와 이후 수익의 상관 · 종합 점수와 다름</p>
            </div>
            <div className="panel evidence-metric">
              <span className="eyebrow">NEWEY–WEST t</span>
              <strong>{ranking?.ic_t?.toFixed(2) ?? "—"}</strong>
              <p>기간 중첩을 고려한 통계량</p>
            </div>
            <div className="panel evidence-metric">
              <span className="eyebrow">가격 데이터 범위</span>
              <strong>
                {report.prices_available ?? 0}
                <small> / {report.universe_count ?? 0}</small>
              </strong>
              <p>현재 구성 기준 · 생존 편향 존재</p>
            </div>
          </div>
          <section className="panel">
            <SectionHead
              title="분위별 63일 초과수익"
              detail="가격 모멘텀 팩터 · 유니버스 평균 대비 · %"
            />
            {chart.length ? (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="name" stroke="var(--muted)" fontSize={11} />
                    <YAxis stroke="var(--muted)" fontSize={11} />
                    <Tooltip
                      contentStyle={{
                        background: "var(--panel)",
                        border: "1px solid var(--border)",
                        color: "var(--foreground)",
                      }}
                    />
                    <Bar
                      dataKey="return"
                      name="초과수익 %"
                      fill="var(--foreground)"
                      radius={[3, 3, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState title="충분한 분위별 표본이 없습니다" />
            )}
          </section>
          <section className="panel">
            <SectionHead
              title="월별 IC"
              detail="가격 모멘텀 · 63일 · 중첩 수익률"
            />
            {ranking?.ic_series?.length ? (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={ranking.ic_series}>
                    <CartesianGrid stroke="var(--border)" />
                    <XAxis
                      dataKey="date"
                      stroke="var(--muted)"
                      fontSize={10}
                      tickFormatter={(v) => String(v).slice(0, 7)}
                    />
                    <YAxis stroke="var(--muted)" fontSize={11} />
                    <ReferenceLine y={0} stroke="var(--muted)" />
                    <Tooltip
                      contentStyle={{
                        background: "var(--panel)",
                        border: "1px solid var(--border)",
                      }}
                    />
                    <Line
                      dataKey="ic"
                      name="IC"
                      stroke="var(--foreground)"
                      dot={false}
                      connectNulls={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <EmptyState
                title="월별 IC 시계열이 없습니다"
                detail="검증 배치를 실행하세요."
              />
            )}
          </section>
          <section className="panel">
            <SectionHead
              title="진입 방식과 청산 A · B · C"
              detail="헤드라인은 승률이 아닌 비용 차감 기대값입니다."
            />
            <div className="grid-three">
              {Object.entries(report.events ?? {}).map(([name, value]) => (
                <div className="journal-card" key={name}>
                  <h3>
                    {name
                      .replace("pullback", "눌림목")
                      .replace("momentum", "모멘텀")}
                  </h3>
                  <p>
                    기대값{" "}
                    <strong
                      className={
                        (value.expected_r ?? 0) >= 0 ? "positive" : "negative"
                      }
                    >
                      {value.expected_r == null
                        ? "—"
                        : `${value.expected_r.toFixed(3)} R`}
                    </strong>
                  </p>
                  <p>
                    무작위 진입 {value.random_expected_r?.toFixed(3) ?? "—"} R ·
                    N={value.n}
                  </p>
                </div>
              ))}
            </div>
            <Warnings
              items={[
                report.default_exit_reason ??
                  "기본 청산 방식은 자동으로 선택하지 않았습니다.",
                "가격 팩터 결과를 종합 점수의 검증 근거로 사용하지 않습니다.",
              ]}
            />
          </section>
        </div>
      ) : !r.loading && !r.error ? (
        <section className="panel">
          <EmptyState
            title="아직 게시된 검증 결과가 없습니다"
            detail="검증 배치 실행 후 데이터 기간, 비용 가정, 신뢰구간과 함께 표시됩니다. 결과가 없다고 근거가 있는 것으로 간주하지 않습니다."
          />
        </section>
      ) : null}
    </>
  );
}
export function Market() {
  const [market, setMarket] = useState("us");
  const r = useResource<MarketData>(`/market/${market}/regime`);
  const regime = r.result?.data.regime;
  return (
    <>
      <PageHead
        overline="MARKET CONTEXT"
        title="시장 국면"
        detail="시장 국면은 종합 점수가 아닌 포지션 크기에만 반영합니다."
      />
      <div className="grid-two">
        <MarketCard market="us" />
        <MarketCard market="kr" />
      </div>
      <section className="panel" style={{ marginTop: 24 }}>
        <SectionHead
          title="국면의 구성 요소"
          action={
            <div className="segmented">
              {[
                ["us", "미국"],
                ["kr", "한국"],
              ].map(([v, l]) => (
                <button
                  key={v}
                  className={market === v ? "active" : ""}
                  onClick={() => setMarket(v)}
                >
                  {l}
                </button>
              ))}
            </div>
          }
        />
        <ResourceError resource={r} />
        {regime ? (
          <>
            <dl className="details-list">
              {Object.entries(regime.components).map(([key, value]) => (
                <div key={key}>
                  <dt>
                    {{
                      above_ma200: "지수 종가 > 200일선",
                      ma50_above_ma200: "50일선 > 200일선",
                      ma200_rising: "200일선 상승",
                    }[key] ?? key}
                  </dt>
                  <dd>{value > 0 ? "조건 충족" : "미충족"}</dd>
                </div>
              ))}
              <div>
                <dt>USD / KRW</dt>
                <dd>
                  {money(r.result?.data.fx.data, "KRW")} 원{" "}
                  <Badge>{r.result?.data.fx.status ?? "미확인"}</Badge>
                </dd>
              </div>
            </dl>
            <p className="muted" style={{ fontSize: 12, marginTop: 20 }}>
              {regime.interpretation}
            </p>
          </>
        ) : !r.loading ? (
          <EmptyState title="지수 데이터가 부족합니다" />
        ) : null}
      </section>
      <MarketOverview market={market} />
    </>
  );
}
export function Journal() {
  const r = useResource<Schema["JournalRecord"][]>("/journal");
  const [show, setShow] = useState(false);
  const [message, setMessage] = useState("");
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await post("/journal", {
        symbol: String(form.get("symbol")).toUpperCase(),
        date: form.get("date"),
        side: form.get("side"),
        quantity: Number(form.get("quantity")),
        price: Number(form.get("price")),
        notes: form.get("notes"),
      });
      setShow(false);
      r.reload();
      setMessage("거래 기록을 저장했습니다.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "저장 실패");
    }
  }
  async function remove(id: string) {
    try {
      await api(`/journal/${id}`, { method: "DELETE" });
      r.reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "삭제 실패");
    }
  }
  return (
    <>
      <PageHead
        overline="YOUR DECISION JOURNAL"
        title="기록"
        detail="계획과 실제 행동을 함께 남기세요."
        action={
          <button className="button" onClick={() => setShow(!show)}>
            <Plus size={15} />
            거래 기록
          </button>
        }
      />
      {message && (
        <p role="status" className="success-note">
          {message}
        </p>
      )}
      {show && (
        <form className="panel" onSubmit={save} style={{ marginBottom: 24 }}>
          <SectionHead
            title="실제 거래 기록"
            detail="기록만 저장하며 주문을 실행하지 않습니다."
          />
          <div className="form-grid">
            <label className="form-field">
              종목
              <input name="symbol" placeholder="AAPL" required maxLength={20} />
            </label>
            <label className="form-field">
              거래일
              <input
                name="date"
                type="date"
                required
                defaultValue={new Date().toISOString().slice(0, 10)}
              />
            </label>
            <label className="form-field">
              구분
              <select name="side">
                <option value="buy">매수 기록</option>
                <option value="sell">매도 기록</option>
              </select>
            </label>
            <label className="form-field">
              수량
              <input
                name="quantity"
                type="number"
                inputMode="numeric"
                min="1"
                required
              />
            </label>
            <label className="form-field">
              실제 체결가
              <input
                name="price"
                type="number"
                inputMode="decimal"
                step="any"
                min="0.0001"
                required
              />
            </label>
            <label className="form-field">
              메모
              <input
                name="notes"
                maxLength={4000}
                placeholder="계획을 지켰는지, 무엇을 배웠는지"
              />
            </label>
          </div>
          <div className="form-actions">
            <button className="button primary">기록 저장</button>
            <button
              className="button"
              type="button"
              onClick={() => setShow(false)}
            >
              취소
            </button>
          </div>
        </form>
      )}
      <ResourceError resource={r} />
      {r.result?.data.length ? (
        r.result.data.map((row) => (
          <article className="journal-card" key={row.id}>
            <header>
              <Link href={`/stock/?symbol=${row.symbol}`}>
                <strong>{row.symbol}</strong>
              </Link>
              <div className="badge-row">
                <Badge>{row.side === "buy" ? "매수 기록" : "매도 기록"}</Badge>
                <button
                  className="icon-button"
                  aria-label={`${row.symbol} 기록 삭제`}
                  onClick={() => remove(row.id)}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </header>
            <p>
              {row.date} · {row.score_version}
            </p>
            <div className="journal-meta">
              <span>
                수량<strong>{money(row.quantity)} 주</strong>
              </span>
              <span>
                실제 체결가<strong>{money(row.price)}</strong>
              </span>
              <span>
                진입 시점 점수
                <strong>
                  {Object.keys(row.snapshot ?? {}).length
                    ? "스냅샷 저장됨"
                    : "해당 날짜 스냅샷 없음"}
                </strong>
              </span>
            </div>
            {row.notes && <p>{row.notes}</p>}
            <JournalComparison row={row} />
          </article>
        ))
      ) : !r.loading && !r.error ? (
        <section className="panel">
          <EmptyState
            title="첫 판단을 기록해 보세요"
            detail="실제 거래와 당시 점수를 연결해 계획을 얼마나 지켰는지 살펴볼 수 있습니다."
          />
        </section>
      ) : null}
      <AnalysisHistory />
      <HistoryPanel />
    </>
  );
}
function download(name: string, content: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function SettingsPage() {
  const r = useResource<Schema["Settings"]>("/settings");
  return (
    <>
      <PageHead
        overline="MAKE IT YOURS"
        title="설정"
        detail="테마, 계좌와 비용 가정을 관리합니다."
      />
      <ResourceError resource={r} />
      {r.result && <SettingsForm initial={r.result.data} />}
    </>
  );
}
function SettingsForm({ initial }: { initial: Schema["Settings"] }) {
  const router = useRouter();
  const [draft, setDraft] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  function change<K extends keyof Schema["Settings"]>(
    key: K,
    value: Schema["Settings"][K],
  ) {
    setDraft((d) => ({ ...d, [key]: value }));
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await post<Schema["Settings"]>("/settings", draft);
      applyTheme(result.data);
      setMessage("설정을 저장했습니다.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "저장 실패");
    } finally {
      setBusy(false);
    }
  }
  async function exportData() {
    try {
      const r = await api<Schema["Backup"]>("/export");
      download(
        `goldnam-backup-${new Date().toISOString().slice(0, 10)}.json`,
        JSON.stringify(r.data, null, 2),
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "내보내기 실패");
    }
  }
  async function importData(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 2_000_000) throw new Error("2MB 이하 파일을 선택하세요.");
      await post("/import", JSON.parse(await file.text()));
      setMessage("JSON 기록을 병합했습니다. 설정은 다시 열면 반영됩니다.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "가져오기 실패");
    }
  }
  async function logout() {
    await post("/auth/logout", {});
    localStorage.removeItem("goldnam_last_viewed");
    router.replace("/login/");
  }
  return (
    <div className="stack">
      <form className="panel" onSubmit={save}>
        <SectionHead title="화면과 표시" />
        <div className="settings-row">
          <div>
            <h3>브랜드 테마</h3>
            <p>브랜드 색은 로고에만 적용됩니다.</p>
          </div>
          <div className="theme-options">
            {(["personal", "goldnam"] as const).map((theme) => (
              <button
                type="button"
                key={theme}
                className={`theme-option ${draft.theme === theme ? "active" : ""}`}
                onClick={() => change("theme", theme)}
              >
                <Image src={brands[theme].logo} alt="" width={30} height={30} />
                {brands[theme].name}
              </button>
            ))}
          </div>
        </div>
        <div className="settings-row">
          <div>
            <h3>등락 표시</h3>
            <p>색과 ▲▼ 기호를 함께 사용합니다.</p>
          </div>
          <select
            aria-label="등락 표시"
            value={draft.colors ?? "kr"}
            onChange={(e) =>
              change("colors", e.target.value as "kr" | "international")
            }
          >
            <option value="kr">한국식 · 상승 빨강 / 하락 파랑</option>
            <option value="international">
              국제식 · 상승 초록 / 하락 빨강
            </option>
          </select>
        </div>
        <div className="settings-row">
          <div>
            <h3>계좌 통화</h3>
            <p>표시 단위이며 자동 환전이 아닙니다.</p>
          </div>
          <select
            aria-label="계좌 통화"
            value={draft.currency ?? "KRW"}
            onChange={(e) =>
              change("currency", e.target.value as "KRW" | "USD")
            }
          >
            <option>KRW</option>
            <option>USD</option>
          </select>
        </div>
        <div className="form-grid" style={{ marginTop: 22 }}>
          <label className="form-field">
            계좌 평가액
            <input
              type="number"
              inputMode="decimal"
              min="1"
              value={draft.account ?? 10000000}
              onChange={(e) => change("account", Number(e.target.value))}
            />
          </label>
          <label className="form-field">
            허용 손실 %
            <input
              type="number"
              inputMode="decimal"
              min="0"
              max="6"
              step="0.1"
              value={draft.risk_pct ?? 1}
              onChange={(e) => change("risk_pct", Number(e.target.value))}
            />
          </label>
          <label className="form-field">
            매수 수수료 %
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.001"
              value={(draft.costs?.buy_fee ?? 0.001) * 100}
              onChange={(e) =>
                change("costs", {
                  ...(draft.costs ?? {
                    buy_fee: 0.001,
                    sell_fee: 0.001,
                    sell_tax: 0,
                    slippage: 0.0005,
                  }),
                  buy_fee: Number(e.target.value) / 100,
                })
              }
            />
          </label>
          <label className="form-field">
            매도 수수료 %
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.001"
              value={(draft.costs?.sell_fee ?? 0.001) * 100}
              onChange={(e) =>
                change("costs", {
                  ...(draft.costs ?? {
                    buy_fee: 0.001,
                    sell_fee: 0.001,
                    sell_tax: 0,
                    slippage: 0.0005,
                  }),
                  sell_fee: Number(e.target.value) / 100,
                })
              }
            />
          </label>
          <label className="form-field">
            매도세 %
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={(draft.costs?.sell_tax ?? 0) * 100}
              onChange={(e) =>
                change("costs", {
                  ...(draft.costs ?? {
                    buy_fee: 0.001,
                    sell_fee: 0.001,
                    sell_tax: 0,
                    slippage: 0.0005,
                  }),
                  sell_tax: Number(e.target.value) / 100,
                })
              }
            />
          </label>
          <label className="form-field">
            편도 체결오차 %
            <input
              type="number"
              inputMode="decimal"
              min="0"
              step="0.01"
              value={(draft.costs?.slippage ?? 0.0005) * 100}
              onChange={(e) =>
                change("costs", {
                  ...(draft.costs ?? {
                    buy_fee: 0.001,
                    sell_fee: 0.001,
                    sell_tax: 0,
                    slippage: 0.0005,
                  }),
                  slippage: Number(e.target.value) / 100,
                })
              }
            />
          </label>
        </div>
        <div className="settings-row">
          <div>
            <h3>청산 가정</h3>
            <p>과거 근거가 충분하지 않아 자동 선택하지 않습니다.</p>
          </div>
          <select
            aria-label="청산 가정"
            value={draft.exit_mode ?? ""}
            onChange={(e) =>
              change(
                "exit_mode",
                (e.target.value || null) as "A" | "B" | "C" | null,
              )
            }
          >
            <option value="">미선택 · 비교 근거 확인 필요</option>
            <option value="A">A · 목표 1 전량 / 20일</option>
            <option value="B">B · 절반 + 추적 / 120일</option>
            <option value="C">C · 추적 손절만 / 120일</option>
          </select>
        </div>
        <div className="form-actions">
          <button className="button primary" disabled={busy}>
            {busy ? "저장 중…" : "설정 저장"}
          </button>
        </div>
        {message && (
          <p role="status" className="success-note">
            {message}
          </p>
        )}
      </form>
      <section className="panel">
        <SectionHead
          title="내 기록과 접근 보호"
          detail="관심종목·일지·설정을 JSON으로 옮길 수 있습니다."
        />
        <div className="form-actions">
          <button className="button" onClick={exportData}>
            <ArrowDownToLine size={16} />
            JSON 내보내기
          </button>
          <label className="button">
            <ArrowUpFromLine size={16} />
            JSON 가져오기
            <input
              className="sr-only"
              type="file"
              accept="application/json,.json"
              onChange={(e) => importData(e.target.files?.[0])}
            />
          </label>
          <button className="button" onClick={logout}>
            로그아웃
          </button>
        </div>
        <p className="plan-source" style={{ marginTop: 20 }}>
          로그인 보호 · 세션 30일 · 비밀번호는 서버에 표준 해시로 보관합니다.
          공개용으로 바꿀 때 Goldnam 테마와 면책 문구를 확인하세요.
        </p>
      </section>
    </div>
  );
}
export { Trade } from "./trade-lab";

function MarketOverview({ market }: { market: string }) {
  const r = useResource<{
    macro: {
      symbol: string;
      label: string;
      unit: string;
      value: number | null;
      source: Schema["Source"];
    }[];
    heatmap: { symbol: string; weight: number; change_pct: number | null }[];
    as_of: string | null;
    note: string;
  }>(`/market/${market}/overview`);
  return (
    <section className="panel" style={{ marginTop: 22 }}>
      <SectionHead
        title="시장 참고 지표"
        detail={r.result?.data.as_of ?? "출처별 조회 시각"}
      />
      <ResourceError resource={r} />
      <div className="grid-two">
        {r.result?.data.macro.map((m) => (
          <div className="journal-card" key={m.symbol}>
            <h3>{m.label}</h3>
            <p className="score-number">
              {money(m.value)} {m.unit}
            </p>
            <DataBadge source={m.source} />
          </div>
        ))}
      </div>
      <SectionHead
        title="유니버스 히트맵"
        detail="시가총액 제곱근 크기 · 등락 색과 기호"
      />
      {r.result?.data.heatmap.length ? (
        <div className="heatmap">
          {r.result.data.heatmap.map((t) => (
            <Link
              key={t.symbol}
              href={`/stock/?symbol=${t.symbol}`}
              style={{ flexGrow: t.weight }}
              className={(t.change_pct ?? 0) >= 0 ? "positive" : "negative"}
            >
              <strong>{t.symbol}</strong>
              <span>{pct(t.change_pct)}</span>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          title="시가총액이 있는 배치 데이터가 없습니다"
          detail="재무 키 설정 후 배치를 실행하세요. 결측 크기를 임의로 채우지 않습니다."
        />
      )}
      <p className="plan-source">{r.result?.data.note}</p>
    </section>
  );
}
