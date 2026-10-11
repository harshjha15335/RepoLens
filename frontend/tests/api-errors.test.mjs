import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Exercise the actual client with real Response streams, without a browser.
const source = await readFile(new URL("../app/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
});
const { api } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

for (const [name, body, expected] of [
  ["plain text", "Backend unavailable", "Backend unavailable"],
  ["HTML proxy error", "<html>Bad gateway</html>", "<html>Bad gateway</html>"],
  ["JSON error", '{"error":"Repository not found"}', "Repository not found"],
  ["JSON detail", '{"detail":"Invalid archive"}', "Invalid archive"],
  ["structured detail", '{"detail":[{"msg":"Field required"}]}', '[{"msg":"Field required"}]'],
  ["empty response", "", "HTTP error 502"],
  ["null JSON", "null", "HTTP error 502"],
]) {
  test(`reports ${name} without reading the response twice`, async (t) => {
    const response = new Response(body, { status: 502 });
    t.mock.method(globalThis, "fetch", async () => response);
    await assert.rejects(api.getRepositories(), (error) => {
      assert.equal(error.message, expected);
      assert.equal(error instanceof TypeError, false);
      return true;
    });
    assert.equal(response.bodyUsed, true);
  });
}

test("successful responses still return repository data", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response('{"repositories":[],"total":0}'));
  assert.deepEqual(await api.getRepositories(), []);
});
