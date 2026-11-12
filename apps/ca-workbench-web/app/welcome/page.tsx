import type { Metadata } from "next";
import { Landing } from "../../components/landing/Landing";

export const metadata: Metadata = { title: "Kosh AI · The work arrives done. A human files.", description: "Kosh AI reads a small business's bills, does the GST, TDS and e-way bill arithmetic, chases suppliers and explains it in the owner's language. A human stamps it." };
export default function Welcome() { return <Landing />; }
