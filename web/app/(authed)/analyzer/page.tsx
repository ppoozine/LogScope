import { cookies } from "next/headers";

import { AnalyzerView } from "@/components/analyzer/analyzer-view";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

type LogTypeDetail = components["schemas"]["LogTypeDetail"];
type FieldSchemaRead = components["schemas"]["FieldSchemaRead"];

type SearchParams = { log_type_id?: string; sample_id?: string };

type Preload = {
  log_type_id: string;
  vrl_code: string | null;
  engine_version: "0.25" | "0.32";
  sample_raw_log: string | null;
  fields: FieldSchemaRead[];
};

async function loadPreload(
  logTypeId: string,
  sampleId: string | null,
  session: string,
): Promise<Preload | null> {
  try {
    const r = await apiFetch<{ data: LogTypeDetail }>(`/api/v1/library/log_types/${logTypeId}`, {
      cookie: `session=${session}`,
    });
    const lt = r.data;
    const sample = sampleId
      ? (lt.samples?.find((s) => s.id === sampleId) ?? lt.samples?.[0])
      : lt.samples?.[0];
    return {
      log_type_id: lt.id,
      vrl_code: lt.current_parse_rule?.vrl_code ?? null,
      engine_version: (lt.current_parse_rule?.engine_version as "0.25" | "0.32") ?? "0.32",
      sample_raw_log: sample?.raw_log ?? null,
      fields: lt.fields ?? [],
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

// Frontend can't read the backend's ANTHROPIC_API_KEY (separate process,
// separate .env). Ask the backend instead.
async function loadMatchAvailability(session: string): Promise<boolean> {
  try {
    const r = await apiFetch<{ data: { available: boolean } }>(
      "/api/v1/analyzer/match-availability",
      { cookie: `session=${session}` },
    );
    return r.data.available;
  } catch {
    return false;
  }
}

export default async function AnalyzerPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await searchParams;
  const cookieStore = await cookies();
  const session = cookieStore.get("session")?.value ?? "";

  const [preload, matchAvailable] = await Promise.all([
    sp.log_type_id ? loadPreload(sp.log_type_id, sp.sample_id ?? null, session) : null,
    loadMatchAvailability(session),
  ]);

  return <AnalyzerView preload={preload} noKey={!matchAvailable} />;
}
