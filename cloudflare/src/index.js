import manifest from "../../bundle/manifest.json";

function json(value, status = 200) {
  return new Response(JSON.stringify(value, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function authorized(request, env) {
  const expected = `Bearer ${env.DCORE_ACTION_KEY}`;
  const supplied = request.headers.get("authorization") || "";
  if (expected.length !== supplied.length) return false;

  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= expected.charCodeAt(index) ^ supplied.charCodeAt(index);
  }
  return difference === 0;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, 405);
    }
    if (!authorized(request, env)) {
      return json({ error: "unauthorized" }, 401);
    }

    if (url.pathname === "/v1/health") {
      return json({ status: "ok", service: "dcore-update-bridge" });
    }

    if (url.pathname === "/v1/latest") {
      return json(manifest);
    }

    return json({ error: "not_found" }, 404);
  },
};
