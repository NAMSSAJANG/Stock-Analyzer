import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Market } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="market">
      <Suspense fallback={<Loading />}>
        <Market />
      </Suspense>
    </Shell>
  );
}
