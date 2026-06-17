// Identifiants de modèles Anthropic — centralisés pour éviter les alias non datés
// que l'API peut rejeter (cf. fix étage 4 worker : « claude-haiku-4-5 » → id daté).
// Toute route/lib web qui appelle l'API Anthropic doit utiliser ces constantes.
export const HAIKU_MODEL = "claude-haiku-4-5-20251001";
export const SONNET_MODEL = "claude-sonnet-4-6";
