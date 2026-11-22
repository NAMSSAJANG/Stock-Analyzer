export default function Home() {
  return <main>
    <h1>Goldnam Sachs</h1>
    <p>개발 준비 중 · v{process.env.NEXT_PUBLIC_APP_VERSION}</p>
    <p>분석 기능은 아직 제공하지 않습니다.</p>
    <footer>
      <p>정보 제공·학습 목적이며 투자 조언이 아닙니다.</p>
      <p>Goldnam Sachs는 개인 프로젝트이며 Goldman Sachs와 관련이 없습니다.</p>
    </footer>
  </main>;
}
