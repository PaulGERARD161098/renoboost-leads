import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ReSign CRM",
  description: "Interface commerciale — prospection ReSign Énergie",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
