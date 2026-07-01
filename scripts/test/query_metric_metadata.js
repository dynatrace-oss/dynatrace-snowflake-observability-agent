// Ad-hoc function executed via `dtctl exec function -f` inside the App Engine
// sandbox — this gives automatic platform (OAuth) authentication with no
// token handling required. Queries the unit Dynatrace actually recognized for
// a single metric key using the Grail Query API's `enrich=metric-metadata`
// parameter (see https://developer.dynatrace.com/develop/sdks/client-query/).
//
// `dtctl query`'s DQL "timeseries" JSON has no metadata.metrics[].unit field
// at all — only the enrich=metric-metadata parameter populates it, and dtctl
// does not currently expose a flag to pass that through, hence this ad-hoc
// function as a workaround.
//
// Used exclusively by scripts/test/verify_metric_units.sh — not run standalone.
//
// Usage:
//   dtctl exec function -f scripts/test/query_metric_metadata.js \
//       --payload '{"metricKey":"process.cpu.utilization"}' -o json

import { queryExecutionClient } from "@dynatrace-sdk/client-query";

export default async function (payload) {
  const metricKey = payload.metricKey;
  const query = `timeseries sum(${metricKey}), from: -90m`;

  let response = await queryExecutionClient.queryExecute({ body: { query }, enrich: "metric-metadata" });
  while (response.state === "RUNNING" || response.state === "NOT_STARTED") {
    response = await queryExecutionClient.queryPoll({ requestToken: response.requestToken, enrich: "metric-metadata" });
  }

  if (response.state !== "SUCCEEDED" || !response.result) {
    return { unit: null, displayName: null, state: response.state };
  }

  const metrics = response.result.metadata.metrics || [];
  const match = metrics.find((m) => m["metric.key"] === metricKey);
  return {
    unit: match && match.unit !== undefined ? match.unit : null,
    displayName: match && match.displayName !== undefined ? match.displayName : null,
  };
}
