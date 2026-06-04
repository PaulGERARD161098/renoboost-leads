import { redirect } from "next/navigation";
import { Nav } from "@/components/nav";
import { AssistantWidget } from "@/components/assistant-widget";
import { WelcomeModal } from "@/components/welcome-modal";
import { createClient } from "@/lib/supabase/server";
import { getSessionBriefing } from "@/lib/briefing";

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

  return (
    <div className="min-h-screen">
      <Nav email={user.email ?? null} />
      {/* Décalage = largeur de la sidebar repliée (elle s'étend en overlay au survol). */}
      <main className="ml-16 px-4 py-6">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
      <AssistantWidget />
      {briefing.shouldShow && <WelcomeModal briefing={briefing} />}
    </div>
  );
}
