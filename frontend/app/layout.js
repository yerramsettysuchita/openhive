import "./globals.css";

export const metadata = {
  title: "OpenHive — An AI engineering team for solo maintainers",
  description:
    "Live production dashboard for OpenHive: a swarm of AI agents that triages issues, reviews PRs, patches CVEs, watches docs, and tracks repository health, with a transparent disagreement protocol and a daily digest.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;0,600;1,400;1,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
