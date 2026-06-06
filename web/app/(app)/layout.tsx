import { redirect } from "next/navigation";
import { Nav } from "@/components/nav";
import { AssistantWidget } from "@/components/assistant-widget";
import { WelcomeModal } from "@/components/welcome-modal";
import { WelcomeV1 } from "@/components/welcome-v1";
import { FeedbackDock } from "@/components/feedback-dock";
import { GuidedTour } from "@/components/guided-tour";
import { DriveMode } from "@/components/drive-mode";
import { createClient } from "@/lib/supabase/server";
import { getSessionBriefing } from "@/lib/briefing";
import { getSystemHealth } from "@/lib/health";
import { isHenry } from "@/lib/welcome-v1";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  // Reprise au login : briefing d'accueil (1×/jour, charte agent-first).
  const briefing = await getSessionBriefing(supabase, {
    id: user.id,
    email: user.email ?? null,
  });

  // Voyant de santé (nom du CRM coloré dans le header).
  const health = await getSystemHealth();

  // Lancement V1 : accueil spécial + boucle de retours, réservés à Henry.
  const henry = isHenry(user.email);
  let showWelcomeV1 = false;
  if (henry) {
    const { data: prof } = await supabase
      .from("profiles")
      .select("welcomed_v1_at")
      .eq("id", user.id)
      .maybeSingle();
    showWelcomeV1 = !prof?.welcomed_v1_at; // joué une seule fois (prochain login)
  }

  return (
    <div className="min-h-screen">
      <Nav email={user.email ?? null} health={health.severite} />
      {/* Décalage = largeur de la sidebar repliée (elle s'étend en overlay au survol). */}
      <main className="ml-16 px-4 py-6">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
      <AssistantWidget />
      <GuidedTour />
      <DriveMode />
      {briefing.shouldShow && <WelcomeModal briefing={briefing} />}
      {showWelcomeV1 && <WelcomeV1 />}
      {henry && <FeedbackDock />}
    </div>
  );
}
