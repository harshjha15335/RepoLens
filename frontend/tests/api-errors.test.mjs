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
  ["generic server error", "Internal Server Error", "The server could not complete this request (HTTP 502). Check that the backend is running and inspect its logs."],
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

test("Git import leaves the branch unset for the repository default", async (t) => {
  const requests = [];
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    requests.push(JSON.parse(options.body));
    return new Response('{}');
  });
  await api.importGit("https://github.com/octocat/Hello-World.git");
  await api.importGit("https://github.com/octocat/Hello-World.git", " master ");
  assert.deepEqual(requests, [
    { url: "https://github.com/octocat/Hello-World.git" },
    { url: "https://github.com/octocat/Hello-World.git", branch: "master" },
  ]);
});

function mockDeadlines(t) {
  const timers = new Map();
  let nextId = 0;
  t.mock.method(globalThis, "setTimeout", (callback, delay) => {
    const id = ++nextId;
    timers.set(id, { callback, delay });
    return id;
  });
  t.mock.method(globalThis, "clearTimeout", (id) => timers.delete(id));
  return timers;
}

for (const [name, invoke, deadline] of [
  ["ordinary request", () => api.getRepositories(), 30_000],
  ["chat request", () => api.sendMessage({ repositoryId: "repo", question: "Explain", tutorMode: "developer" }), 160_000],
]) {
  test(`${name} aborts at its deadline and clears the timer`, async (t) => {
    const timers = mockDeadlines(t);
    let requestSignal;
    t.mock.method(globalThis, "fetch", (_url, options) => {
      requestSignal = options.signal;
      return new Promise((_resolve, reject) => {
        requestSignal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });

    const pending = invoke();
    assert.equal(timers.size, 1);
    const { callback, delay } = [...timers.values()][0];
    assert.equal(delay, deadline);
    callback();
    await assert.rejects(pending, (error) => {
      assert.match(error.message, /Request timed out after \d+ seconds/);
      assert.match(error.message, /The client stopped waiting; server work may continue/);
      return true;
    });
    assert.equal(requestSignal.aborted, true);
    assert.equal(timers.size, 0);
  });
}

test("deadline remains active while the response body is read, then clears", async (t) => {
  const timers = mockDeadlines(t);
  let bodyController;
  t.mock.method(globalThis, "fetch", async () => new Response(new ReadableStream({
    start(controller) { bodyController = controller; },
  })));

  const pending = api.getRepositories();
  await new Promise(setImmediate);
  assert.equal(timers.size, 1);
  bodyController.enqueue(new TextEncoder().encode('{"repositories":[],"total":0}'));
  bodyController.close();
  assert.deepEqual(await pending, []);
  assert.equal(timers.size, 0);
});
