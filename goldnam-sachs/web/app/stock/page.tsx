import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Stock } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="stock">
      <Suspense fallback={<Loading />}>
        <Stock />
      </Suspense>
    </Shell>
  );
}
