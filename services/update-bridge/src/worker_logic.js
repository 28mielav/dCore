export function json(value, status = 200) {
  return new Response(JSON.stringify(value, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function configuredKey(env) {
  const key = env?.DCORE_ACTION_KEY;
  return typeof key === "string" && key.trim().length > 0 ? key : null;
}

export function authorized(request, env) {
  const key = configuredKey(env);
  if (!key) {
    return { allowed: false, status: 503, error: "bridge_misconfigured" };
  }
  const expected = `Bearer ${key}`;
  const supplied = request.headers.get("authorization") || "";
  if (expected.length !== supplied.length) {
    return { allowed: false, status: 401, error: "unauthorized" };
  }
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= expected.charCodeAt(index) ^ supplied.charCodeAt(index);
  }
  return difference === 0
    ? { allowed: true }
    : { allowed: false, status: 401, error: "unauthorized" };
}

export function createHandler(manifest) {
  return async function fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/privacy") {
      return new Response(
        "dCore Update Bridge Privacy Policy\n\n" +
          "This private read-only service does not collect, store, sell, or share personal data. " +
          "It receives an authorization header solely to validate access and returns the current verified dCore release manifest. " +
          "Cloudflare may process standard network metadata according to its infrastructure policies.\n",
        {
          status: 200,
          headers: {
            "content-type": "text/plain; charset=utf-8",
            "cache-control": "public, max-age=3600",
          },
        },
      );
    }
    if (request.method !== "GET") {
      return json({ error: "method_not_allowed" }, 405);
    }
    const access = authorized(request, env);
    if (!access.allowed) {
      return json({ error: access.error }, access.status);
    }
    if (url.pathname === "/v1/health") {
      return json({ status: "ok", service: "dcore-update-bridge" });
    }
    if (url.pathname === "/v1/latest") {
      return json(manifest);
    }
    return json({ error: "not_found" }, 404);
  };
}
