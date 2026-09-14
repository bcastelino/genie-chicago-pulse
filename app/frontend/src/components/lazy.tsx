import { Suspense, lazy } from "react";
import type { ComponentProps } from "react";
import { Skeleton } from "./States";

// Recharts (~large) and d3-geo are only pulled in when a chart or the map
// actually renders, keeping the initial bundle lean.
const AutoChartImpl = lazy(() =>
  import("./AutoChart").then((m) => ({ default: m.AutoChart })),
);
const ChoroplethImpl = lazy(() =>
  import("./ChoroplethMap").then((m) => ({ default: m.ChoroplethMap })),
);

export function AutoChart(props: ComponentProps<typeof AutoChartImpl>) {
  return (
    <Suspense fallback={<Skeleton height={300} radius={8} />}>
      <AutoChartImpl {...props} />
    </Suspense>
  );
}

export function ChoroplethMap(props: ComponentProps<typeof ChoroplethImpl>) {
  return (
    <Suspense fallback={<Skeleton height={440} radius={8} />}>
      <ChoroplethImpl {...props} />
    </Suspense>
  );
}
