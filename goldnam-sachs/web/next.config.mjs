import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../engine/goldnam_engine/_version.py", import.meta.url), "utf8");
const version = source.match(/^APP_VERSION = "([^"]+)"/m)?.[1];
if (!version) throw new Error("Engine app version is missing");

const config = {
  output: "export",
  env: { NEXT_PUBLIC_APP_VERSION: version },
};
export default config;
