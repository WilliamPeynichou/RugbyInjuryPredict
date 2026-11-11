import type { Metadata } from "next";
import { DM_Sans, DM_Serif_Display } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./layout.module.css";
import { Reveal } from "@/components/Reveal";
import "./globals.css";

const serif = DM_Serif_Display({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-dm-serif",
  display: "swap",
});

const sans = DM_Sans({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Risque de blessure par poste en Top 14",
  description:
    "Blessures entraînant au moins 2 matchs d'absence, saisons 2022 à 2025. Données agrégées par poste.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr" className={`${serif.variable} ${sans.variable}`}>
      <body>
        <a className={styles.skip} href="#contenu">
          Aller au contenu
        </a>
        <header className={styles.header}>
          <nav className={styles.nav} aria-label="Navigation principale">
            <Link href="/" className={styles.navLink}>
              Tableau de bord
            </Link>
            <Link href="/methodologie" className={styles.navLink}>
              Méthodologie
            </Link>
          </nav>
        </header>
        <main id="contenu" className={styles.main}>
          <Reveal>{children}</Reveal>
        </main>
        <footer className={styles.footer}>
          <div className={styles.grain} aria-hidden="true" />
          <div className={styles.footerInner}>
            <p className={styles.footerText}>
              Association statistique, non causale. Données agrégées par poste :
              aucun joueur identifiable, aucun cookie. Ce site ne remplace pas
              l&apos;avis du staff médical.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
