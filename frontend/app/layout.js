export const metadata = {
  title: "OpenHive — AI agent swarm for open source maintainers",
  description:
    "Live dashboard for OpenHive: repository health, agent activity, the Transparent Disagreement Protocol, and the daily digest.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
