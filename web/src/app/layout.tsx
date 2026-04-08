import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { shadcn } from "@clerk/ui/themes";
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EventFinder AI",
  description: "Discover free events with your friends",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <meta
          httpEquiv="Content-Security-Policy"
          content="default-src 'self' https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; connect-src 'self' https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com https://api.event-searcher.com; frame-src 'self' https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; img-src 'self' data: blob: https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; style-src 'self' 'unsafe-inline' https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; font-src 'self' data: https://clerk.event-searcher.com https://*.clerk.accounts.dev https://*.clerk.com; worker-src 'self' blob:;"
        />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ClerkProvider dynamic appearance={{ theme: shadcn }}>
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
