import Link from "next/link";
export default function NotFound() { return <section className="empty"><p className="eyebrow">404 / CLIENT NOT FOUND</p><h1>This record isn’t in the workspace.</h1><p>Return to the matrix to choose one of the 80 demo clients.</p><Link href="/">Back to Exception Matrix →</Link></section>; }
