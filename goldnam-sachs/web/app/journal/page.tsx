import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { Journal } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="journal">
      <Suspense fallback={<Loading />}>
        <Journal />
      </Suspense>
    </Shell>
  );
}
