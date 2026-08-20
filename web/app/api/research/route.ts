import { desc, eq } from "drizzle-orm";
import { ensureSchema, getDb } from "../../../db";
import { researchRuns } from "../../../db/schema";

export async function GET() {
  try {
    await ensureSchema();
    const rows = await getDb().select().from(researchRuns).orderBy(desc(researchRuns.createdAt)).limit(30);
    const items = rows.map((row) => {
      try {
        return { ...row, report: JSON.parse(row.reportJson) };
      } catch {
        return { ...row, report: null };
      }
    });
    return Response.json({ items });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "读取失败" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json() as {
      run_id?: string;
      security?: { code?: string; exchange?: string };
      as_of?: string;
      synthesis?: { company_quality?: string; confidence?: number };
      valuation?: { view?: string; pricing_status?: string };
    };
    const runId = payload.run_id?.trim();
    const code = payload.security?.code?.trim();
    const exchange = payload.security?.exchange?.trim();
    const asOf = payload.as_of?.trim();
    const quality = payload.synthesis?.company_quality?.trim();
    const valuation = payload.valuation?.view?.trim();
    const confidence = payload.synthesis?.confidence;
    const rating = quality && valuation ? `${quality}/${valuation}` : undefined;
    if (!runId || !code || !exchange || !asOf || !rating || typeof confidence !== "number") {
      return Response.json({ error: "研究结果字段不完整" }, { status: 400 });
    }
    const symbol = `${code}.${exchange}`;
    await ensureSchema();
    const db = getDb();
    await db.insert(researchRuns).values({
      runId,
      symbol,
      asOf,
      rating,
      confidence,
      reportJson: JSON.stringify(payload),
    }).onConflictDoUpdate({
      target: researchRuns.runId,
      set: { symbol, asOf, rating, confidence, reportJson: JSON.stringify(payload) },
    });
    const [item] = await db.select().from(researchRuns).where(eq(researchRuns.runId, runId)).limit(1);
    return Response.json({ item }, { status: 201 });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "保存失败" }, { status: 500 });
  }
}
