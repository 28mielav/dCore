import manifest from "../../../knowledge/manifest.json";
import { createHandler } from "./worker_logic.js";

export default {
  fetch: createHandler(manifest),
};
