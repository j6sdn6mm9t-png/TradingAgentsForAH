import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), {
    ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
  }, { waitUntil() {}, passThroughOnException() {} });
}

test("server-renders the A/H research dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /A\+H 股公司研究系统/);
  assert.match(html, /公司研究总览/);
  assert.match(html, /先理解公司，再选择指标/);
  assert.match(html, /估值与安全边际/);
  assert.match(html, /A \+ H 全市场/);
  assert.doesNotMatch(html, /1–3 个月|当前仓位|模拟组合|基本面质量.*40%/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|SkeletonPreview/);
});
