// Version de l'app, source de vérité unique.
// Convention : on incrémente le MINEUR (1.x.0) à chaque PR livrée — la version
// affichée progresse donc V1.0 → V1.1 → V1.2 … (cf. web/CHANGELOG.md).
// Le SHA du build est injecté par Vercel (cf. next.config.ts → NEXT_PUBLIC_BUILD_SHA).
export const APP_VERSION = "1.10.0";

const sha = (process.env.NEXT_PUBLIC_BUILD_SHA ?? "").slice(0, 7);
export const BUILD_SHA: string | null = sha || null;

/** Libellé affiché : « v1.0.0 · a1b2c3d » (SHA omis en local s'il est absent). */
export function versionLabel(): string {
  return BUILD_SHA ? `v${APP_VERSION} · ${BUILD_SHA}` : `v${APP_VERSION}`;
}
