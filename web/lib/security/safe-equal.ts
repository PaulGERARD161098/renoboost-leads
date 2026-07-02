import { timingSafeEqual } from "crypto";

// Comparaison de chaînes à temps constant (anti timing side-channel) : renvoie
// true seulement si a et b sont égaux, sans fuiter d'information par la durée.
// La comparaison de longueur reste nécessaire (timingSafeEqual exige des buffers
// de même taille) ; la longueur d'un secret n'est pas une donnée sensible.
export function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}
