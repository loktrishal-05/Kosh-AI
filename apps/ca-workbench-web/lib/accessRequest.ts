import type { AuthText } from "./authText.ts";

export function accessMailto(recipient: string | undefined, data: FormData, t: AuthText): string | null {
  const email = recipient?.trim();
  if (!email || !/^[^\s@,;?&#]+@[^\s@,;?&#]+\.[^\s@,;?&#]+$/.test(email)) return null;
  const roles: Record<string, string> = { ca: t.roleCA, owner: t.roleOwner, other: t.roleOther };
  const body = [
    `${t.name}: ${String(data.get("name") ?? "").trim()}`,
    `${t.email}: ${String(data.get("email") ?? "").trim()}`,
    `${t.firm}: ${String(data.get("firm") ?? "").trim()}`,
    `${t.role}: ${roles[String(data.get("role"))] ?? t.roleOther}`,
    `${t.note}: ${String(data.get("note") ?? "").trim()}`,
    "", t.consentSummary
  ].join("\r\n");
  return `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(t.emailSubject)}&body=${encodeURIComponent(body)}`;
}
