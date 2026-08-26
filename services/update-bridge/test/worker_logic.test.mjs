import assert from "node:assert/strict";
import test from "node:test";

import { createHandler } from "../src/worker_logic.js";

const handler = createHandler({ name: "dCore", status: "verified" });

async function response(path, env, headers = {}, method = "GET") {
  return handler(new Request(`https://bridge.example${path}`, { method, headers }), env);
}

test("missing or empty secret fails closed", async () => {
  for (const env of [{}, { DCORE_ACTION_KEY: "" }, { DCORE_ACTION_KEY: "   " }]) {
    const result = await response("/v1/latest", env, { authorization: "Bearer undefined" });
    assert.equal(result.status, 503);
    assert.deepEqual(await result.json(), { error: "bridge_misconfigured" });
  }
});

test("only the configured bearer can read protected endpoints", async () => {
  const env = { DCORE_ACTION_KEY: "correct-secret" };
  const rejected = await response("/v1/latest", env, { authorization: "Bearer wrong-secret" });
  assert.equal(rejected.status, 401);
  const allowed = await response("/v1/latest", env, { authorization: "Bearer correct-secret" });
  assert.equal(allowed.status, 200);
  assert.deepEqual(await allowed.json(), { name: "dCore", status: "verified" });
});

test("public privacy and protected endpoint semantics remain stable", async () => {
  assert.equal((await response("/privacy", {})).status, 200);
  assert.equal((await response("/v1/health", { DCORE_ACTION_KEY: "x" }, {}, "POST")).status, 405);
  assert.equal((await response("/missing", { DCORE_ACTION_KEY: "x" }, { authorization: "Bearer x" })).status, 404);
  assert.equal((await response("/v1/health", { DCORE_ACTION_KEY: "x" }, { authorization: "Bearer x" })).status, 200);
});
