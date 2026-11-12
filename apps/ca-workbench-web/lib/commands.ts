export type Command = { href: string; label: string; keywords?: string };

export function fuzzyFilter(commands: Command[], query: string): Command[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return commands;
  return commands.map((command, index) => {
    const text = `${command.label} ${command.href} ${command.keywords ?? ""}`.toLocaleLowerCase();
    let cursor = 0, gaps = 0;
    for (const char of needle) {
      const at = text.indexOf(char, cursor);
      if (at < 0) return { command, index, score: Infinity };
      gaps += at - cursor; cursor = at + 1;
    }
    return { command, index, score: text.includes(needle) ? text.indexOf(needle) : text.length + gaps };
  }).filter(result => Number.isFinite(result.score)).sort((a, b) => a.score - b.score || a.index - b.index).map(result => result.command);
}
