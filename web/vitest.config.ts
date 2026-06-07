import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Tests unitaires des helpers purs côté web (scoring potentiels, garde-fous de
// ciblage, signaux VE). Node env, pas de DOM : ce sont des fonctions pures.
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
