import { desc, eq } from "drizzle-orm";
import { ensureSchema, getDb } from "../../../db";
import { watchlist } from "../../../db/schema";

function normalizeSymbol(raw: string) {
  let symbol = raw.trim().toUpperCase();
  if (/^\d{5}$/.test(symbol)) symbol = `${symbol}.HK`;
  if (!/^(\d{6}\.(SH|SZ|BJ)|\d{5}\.HK)$/.test(symbol)) {
    throw new Error("代码格式应为 600519.SH、300750.SZ、830799.BJ 或 00700.HK");
  }
  return symbol;
}

export async function GET() {
  try {
    await ensureSchema();
    const items = await getDb().select().from(watchlist).orderBy(desc(watchlist.createdAt));
    return Response.json({ items });
  } catch (error) {
    return Response.json({ error: error instanceof Error ? error.message : "读取失败" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json() as { symbol?: string; name?: string; market?: string };
    const symbol = normalizeSymbol(payload.symbol || "");
    const market = symbol.endsWith(".HK") ? "港股" : "A股";
    await ensureSchema();
    const db = getDb();
    await db.insert(watchlist).values({ symbol, name: payload.name?.trim() || symbol, market }).onConflictDoNothing();
    const [item] = await db.select().from(watchlist).where(eq(watchlist.symbol, symbol)).limit(1);
    return Response.json({ item }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "保存失败";
    return Response.json({ error: message }, { status: message.includes("代码格式") ? 400 : 500 });
  }
}
