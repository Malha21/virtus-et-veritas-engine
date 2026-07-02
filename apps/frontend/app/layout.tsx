import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Virtus et Veritas Engine",
  description: "Inteligência para produção de conhecimento.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
