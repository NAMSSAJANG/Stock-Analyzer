import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Evidence } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="evidence">
      <Suspense fallback={<Loading />}>
        <Evidence />
      </Suspense>
    </Shell>
  );
}
