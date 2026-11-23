import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Trade } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="trade">
      <Suspense fallback={<Loading />}>
        <Trade />
      </Suspense>
    </Shell>
  );
}
