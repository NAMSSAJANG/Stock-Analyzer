import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Screener } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="screener">
      <Suspense fallback={<Loading />}>
        <Screener />
      </Suspense>
    </Shell>
  );
}
