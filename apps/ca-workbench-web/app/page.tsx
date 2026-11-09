import { Matrix } from "../components/Matrix";
import { clients } from "../lib/mock";
export default function Home() { return <Matrix initialClients={clients} />; }
