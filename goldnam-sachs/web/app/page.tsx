import { Suspense } from "react";
import { Shell } from "../components/shell";
import { Home } from "../components/pages";
import { Loading } from "../components/ui";
export default function Page() {
  return (
    <Shell page="home">
      <Suspense fallback={<Loading />}>
        <Home />
      </Suspense>
    </Shell>
  );
}
