import { redirect } from "next/navigation";
import { Nav } from "@/components/nav";
import { AssistantWidget } from "@/components/assistant-widget";
import { createClient } from "@/lib/supabase/server";

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

  return (
    <div className="min-h-screen">
      <Nav email={user.email ?? null} />
      {/* Décalage = largeur de la sidebar repliée (elle s'étend en overlay au survol). */}
      <main className="ml-16 px-4 py-6">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
      <AssistantWidget />
    </div>
  );
}
