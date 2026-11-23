import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { SearchPage } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="search">
      <Suspense fallback={<Loading />}>
        <SearchPage />
      </Suspense>
    </Shell>
  );
}
