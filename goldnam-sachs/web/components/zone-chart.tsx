"use client";
import { useEffect, useRef } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Schema } from "../lib/api";
export default function ZoneChart({
  bars,
  zones,
  plan,
}: {
  bars: Schema["PriceBar"][];
  zones?: Schema["ZoneSet"] | null;
  plan?: Schema["SetupScore"] | null;
}) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!host.current || !bars.length) return;
    const root = host.current;
    const css = getComputedStyle(document.documentElement);
    const color = (name: string) => css.getPropertyValue(name).trim();
    const chart = createChart(root, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: color("--panel") },
        textColor: color("--muted"),
        fontFamily: "Pretendard",
        fontSize: 10,
        attributionLogo: true,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: color("--chart-grid") },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.08, bottom: 0.22 },
      },
      timeScale: { borderVisible: false, timeVisible: false },
      crosshair: {
        vertLine: { color: color("--muted") },
        horzLine: { color: color("--muted") },
      },
      handleScroll: { horzTouchDrag: true, vertTouchDrag: false },
      handleScale: {
        pinch: true,
        mouseWheel: true,
        axisPressedMouseMove: true,
      },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: color("--positive"),
      downColor: color("--negative"),
      borderVisible: false,
      wickUpColor: color("--positive"),
      wickDownColor: color("--negative"),
    });
    const time = (s: string) =>
      Math.floor(new Date(s).getTime() / 1000) as UTCTimestamp;
    candles.setData(bars.map((b) => ({ ...b, time: time(b.time) })));
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    volume
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.86, bottom: 0 }, visible: false });
    volume.setData(
      bars
        .filter((b) => b.volume != null)
        .map((b) => ({
          time: time(b.time),
          value: b.volume!,
          color:
            b.close >= b.open
              ? `${color("--positive")}55`
              : `${color("--negative")}55`,
        })),
    );
    for (const [period, name] of [
      [50, "--ma50"],
      [200, "--ma200"],
    ] as const) {
      let sum = 0;
      const values: { time: UTCTimestamp; value: number }[] = [];
      bars.forEach((b, i) => {
        sum += b.close;
        if (i >= period) sum -= bars[i - period].close;
        if (i >= period - 1)
          values.push({ time: time(b.time), value: sum / period });
      });
      const series = chart.addSeries(LineSeries, {
        color: color(name),
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      series.setData(values);
    }
    for (const [value, label, token] of [
      [plan?.entry_price, "진입", "--foreground"],
      [plan?.stop_loss, "손절", "--negative"],
      [plan?.target1, "목표 1", "--muted"],
    ] as const) {
      if (value != null)
        candles.createPriceLine({
          price: value,
          color: color(token),
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          title: label,
          axisLabelVisible: true,
        });
    }
    const overlays = [
      ...(zones?.supports ?? []).slice(0, 2),
      ...(zones?.resistances ?? []).slice(0, 2),
    ].map((z) => {
      const el = document.createElement("div");
      el.className = "zone-overlay";
      el.style.background = color(
        z.kind === "support" ? "--support-zone" : "--resistance-zone",
      );
      el.setAttribute("aria-hidden", "true");
      root.appendChild(el);
      return { el, z };
    });
    const repaint = () =>
      overlays.forEach(({ el, z }) => {
        const top = candles.priceToCoordinate(z.high),
          bottom = candles.priceToCoordinate(z.low);
        if (top == null || bottom == null) {
          el.style.display = "none";
          return;
        }
        el.style.display = "block";
        el.style.top = `${Math.max(0, top)}px`;
        el.style.height = `${Math.max(1, Math.min(root.clientHeight, bottom) - Math.max(0, top))}px`;
      });
    chart.timeScale().fitContent();
    chart.timeScale().subscribeVisibleLogicalRangeChange(repaint);
    chart.subscribeCrosshairMove(repaint);
    root.addEventListener("pointermove", repaint);
    const resize = new ResizeObserver(repaint);
    resize.observe(root);
    requestAnimationFrame(repaint);
    return () => {
      resize.disconnect();
      root.removeEventListener("pointermove", repaint);
      overlays.forEach(({ el }) => el.remove());
      chart.remove();
    };
  }, [bars, zones, plan]);
  return (
    <figure>
      <div
        className="price-chart"
        role="group"
        aria-label="일봉 캔들, 50일·200일 이동평균, 지지저항과 계획 가격. 손가락으로 확대·이동할 수 있습니다."
      >
        <div className="chart-inner" ref={host} />
      </div>
      <figcaption className="chart-legend">
        <span>
          <i className="legend-line" />
          MA 50
        </span>
        <span>
          <i className="legend-line long" />
          MA 200
        </span>
        <span>음영: 지지·저항</span>
        <span>점선: 진입·손절·목표</span>
      </figcaption>
    </figure>
  );
}
