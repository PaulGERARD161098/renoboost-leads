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
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      <AssistantWidget />
    </div>
  );
}
