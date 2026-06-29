import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Slide Agent",
  description: "Turn your documents into trustworthy slide presentations.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
