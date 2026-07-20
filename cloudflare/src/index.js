const GITHUB_API = "https://api.github.com";
const REPOSITORY = "28mielav/dcore-updater";

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

async function github(path, env, accept = "application/vnd.github+json") {
  const response = await fetch(`${GITHUB_API}${path}`, {
    headers: {
      accept,
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "user-agent": "dCore-update-bridge/1.0",
      "x-github-api-version": "2022-11-28",
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub API ${response.status}`);
  }
  return response;
}

async function latestManifest(env) {
  const releaseResponse = await github(`/repos/${REPOSITORY}/releases/latest`, env);
  const release = await releaseResponse.json();
  const asset = release.assets.find((candidate) => candidate.name === "manifest.json");
  if (!asset) throw new Error("Latest verified release has no manifest.json asset");

  const manifestResponse = await github(
    `/repos/${REPOSITORY}/releases/assets/${asset.id}`,
    env,
    "application/octet-stream",
  );
  const manifest = await manifestResponse.json();
  return {
    ...manifest,
    release: {
      tag: release.tag_name,
      published_at: release.published_at,
      html_url: release.html_url,
    },
  };
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
      try {
        return json(await latestManifest(env));
      } catch (error) {
        return json({ error: "upstream_failure", detail: String(error.message || error) }, 502);
      }
    }

    return json({ error: "not_found" }, 404);
  },
};

