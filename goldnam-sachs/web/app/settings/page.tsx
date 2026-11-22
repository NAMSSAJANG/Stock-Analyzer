import { Suspense } from "react";
import { Shell } from "../../components/shell";
import { SettingsPage } from "../../components/pages";
import { Loading } from "../../components/ui";
export default function Page() {
  return (
    <Shell page="settings">
      <Suspense fallback={<Loading />}>
        <SettingsPage />
      </Suspense>
    </Shell>
  );
}
