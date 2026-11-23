"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  Activity,
  BookOpen,
  ChartNoAxesCombined,
  FlaskConical,
  House,
  LayoutGrid,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, type Schema } from "../lib/api";
import brands from "../theme/brands.json";
import { Footer } from "./ui";
const NAV = [
  ["home", "/", "홈", House],
  ["screener", "/screener/", "스크리너", LayoutGrid],
  ["search", "/search/", "검색", Search],
  ["evidence", "/evidence/", "점수 근거", FlaskConical],
  ["market", "/market/", "시장", Activity],
  ["trade", "/trade/", "Trade Lab", ChartNoAxesCombined],
  ["journal", "/journal/", "기록", BookOpen],
  ["settings", "/settings/", "설정", Settings],
] as const;
export function applyTheme(settings: Schema["Settings"]) {
  document.documentElement.dataset.theme = settings.theme;
  document.documentElement.dataset.colors = settings.colors;
  localStorage.setItem("goldnam_theme", settings.theme);
  localStorage.setItem("goldnam_colors", settings.colors);
  const manifest = document.querySelector<HTMLLinkElement>(
    'link[rel="manifest"]',
  );
  if (manifest) manifest.href = `/manifest-${settings.theme}.webmanifest`;
  const icon = document.querySelector<HTMLLinkElement>(
    'link[rel="apple-touch-icon"]',
  );
  if (icon) icon.href = `/icons/${settings.theme}-180.png`;
  window.dispatchEvent(new Event("goldnam-theme"));
}
export function Shell({
  page,
  children,
}: {
  page: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const [theme, setTheme] = useState<"personal" | "goldnam">("personal");
  const previous = useRef(0);
  useEffect(() => {
    api<Schema["Settings"]>("/settings")
      .then((r) => {
        applyTheme(r.data);
        setTheme(r.data.theme);
      })
      .catch(() => {});
    const change = () => {
      const t = document.documentElement.dataset.theme;
      setTheme(t === "goldnam" ? "goldnam" : "personal");
    };
    window.addEventListener("goldnam-theme", change);
    const keys = (e: KeyboardEvent) => {
      if (
        (e.target as HTMLElement).closest(
          'input,textarea,select,[contenteditable="true"]',
        )
      )
        return;
      if (e.key === "/") {
        e.preventDefault();
        router.push("/search/");
      }
      if (e.key === "g") previous.current = Date.now();
      else if (Date.now() - previous.current < 1000) {
        if (e.key === "h") router.push("/");
        if (e.key === "s") router.push("/screener/");
      }
    };
    window.addEventListener("keydown", keys);
    if ("serviceWorker" in navigator)
      void navigator.serviceWorker.register("/service-worker.js");
    return () => {
      window.removeEventListener("keydown", keys);
      window.removeEventListener("goldnam-theme", change);
    };
  }, [router]);
  const nav = (mobile = false) =>
    NAV.filter(
      ([id]) =>
        !mobile ||
        ["home", "screener", "search", "journal", "settings"].includes(id),
    ).map(([id, url, label, Icon]) => (
      <Link
        href={url}
        key={id}
        className={page === id ? "active" : ""}
        aria-current={page === id ? "page" : undefined}
      >
        <Icon size={19} />
        <span>{label}</span>
      </Link>
    ));
  return (
    <>
      <a href="#main" className="skip-link">
        본문으로 건너뛰기
      </a>
      <header className="topbar">
        <Link href="/" className="brand">
          <Image
            src={brands[theme].logo}
            alt="Goldnam Sachs"
            width={44}
            height={44}
          />
          <span>
            Goldnam Sachs<small>PRIVATE RESEARCH</small>
          </span>
        </Link>
        <div className="header-right">
          <span className="private">
            <ShieldCheck size={14} />
            개인 리서치
          </span>
          <Link href="/search/" className="header-search">
            <Search size={16} />
            <span>종목 검색</span>
            <kbd>/</kbd>
          </Link>
          <button
            className="icon-button mobile-menu"
            aria-label={menu ? "메뉴 닫기" : "메뉴 열기"}
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>
      <aside className={`sidebar ${menu ? "opened" : ""}`}>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="전체 메뉴">{nav()}</nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          개인용 알파
          <small>
            데이터와 근거를
            <br />
            함께 확인하세요.
          </small>
        </div>
      </aside>
      <main id="main" className="main">
        <div className="content">
          {children}
          <Footer />
        </div>
      </main>
      <nav className="bottom-nav" aria-label="하단 메뉴">
        {nav(true)}
      </nav>
    </>
  );
}
