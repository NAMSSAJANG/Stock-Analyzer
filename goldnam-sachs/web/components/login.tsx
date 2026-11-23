"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { post } from "../lib/api";
import { Footer } from "./ui";
import brands from "../theme/brands.json";
export function Login() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await post("/auth/login", { passcode: password });
      router.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "로그인 실패");
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <div className="login-card">
        <Image
          className="login-logo"
          src={brands.personal.logo}
          alt="Goldnam Sachs"
          width={112}
          height={112}
          priority
        />
        <span className="eyebrow">YOUR PRIVATE RESEARCH DESK</span>
        <h1>
          좋은 판단은
          <br />
          확인할 수 있는 근거에서.
        </h1>
        <p>나만의 리서치 워크스페이스에 로그인하세요.</p>
        <form onSubmit={submit}>
          <label className="form-field">
            앱 비밀번호
            <input
              aria-label="앱 비밀번호"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              maxLength={1024}
            />
          </label>
          {error && (
            <p role="alert" className="caution">
              {error}
            </p>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? "확인 중…" : "로그인"}
            <ArrowRight size={16} />
          </button>
        </form>
        <div className="login-note">
          <LockKeyhole size={12} />
          개인 전용 · 로그인 상태는 30일간 유지됩니다
        </div>
      </div>
      <Footer />
    </main>
  );
}
