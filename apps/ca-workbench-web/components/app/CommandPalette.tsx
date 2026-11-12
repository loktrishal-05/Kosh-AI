"use client";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import { clients } from "../../lib/mock";
import { fuzzyFilter, type Command } from "../../lib/commands";
import type { Lang } from "../../lib/ownerText";
import { WORKBENCH } from "../../lib/workbenchText";
import { navigateView } from "./navigation";

export function CommandPalette({ lang = "en" }: { lang?: Lang }) {
  const router = useRouter(), id = useId(), t = WORKBENCH[lang];
  const dialog = useRef<HTMLDialogElement>(null), input = useRef<HTMLInputElement>(null), returnFocus = useRef<HTMLElement | null>(null);
  const [query, setQuery] = useState(""), [active, setActive] = useState(0);
  const commands: Command[] = [
    { href: "/", label: t.clients }, { href: "/impact", label: t.impact }, { href: "/owner", label: t.owner }, { href: "/books", label: t.books }, { href: "/tally", label: t.tally },
    ...clients.slice(0, 5).map(c => ({ href: `/clients/${c.id}`, label: c.businessName, keywords: `${c.id} ${c.gstin} ${t.client}` })), { href: "/welcome", label: t.welcome },
  ];
  const matches = fuzzyFilter(commands, query);
  function open() {
    if (!dialog.current || dialog.current.open) return;
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery(""); setActive(0); dialog.current.showModal(); input.current?.focus();
  }
  function close() { dialog.current?.close(); }
  function choose(command: Command) { close(); navigateView(command.href, () => router.push(command.href)); }
  useEffect(() => {
    function shortcut(event: globalThis.KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "k") {
        event.preventDefault(); if (dialog.current?.open) close(); else open();
      }
    }
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, []);
  useEffect(() => { dialog.current?.querySelector(`#${CSS.escape(id)}-option-${active}`)?.scrollIntoView({ block: "nearest" }); }, [active, id, query]);
  function keyDown(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault(); if (matches.length) setActive(i => (i + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length);
    } else if (event.key === "Enter" && event.target === input.current) {
      event.preventDefault(); if (matches[active]) choose(matches[active]);
    } else if (event.key === "Tab") {
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('input, button:not([disabled])')].filter(el => el.tabIndex >= 0);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  }
  return <><button type="button" className="command-trigger" onClick={open} aria-haspopup="dialog" aria-keyshortcuts="Control+k Meta+k">{t.commands} <kbd>Ctrl K</kbd></button>
    <dialog ref={dialog} className="command-palette" role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} aria-describedby={`${id}-help`} lang={lang} onKeyDown={keyDown} onCancel={event => { event.preventDefault(); close(); }} onClose={() => returnFocus.current?.focus()}>
      <div className="command-heading"><h2 id={`${id}-title`}>{t.commandTitle}</h2><button type="button" onClick={close}>{t.close} <span aria-hidden="true">×</span></button></div>
      <label htmlFor={`${id}-search`}>{t.commandSearch}</label><input ref={input} id={`${id}-search`} role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls={`${id}-results`} aria-activedescendant={matches[active] ? `${id}-option-${active}` : undefined} autoComplete="off" value={query} onChange={event => { setQuery(event.target.value); setActive(0); }} />
      <ul id={`${id}-results`} role="listbox" aria-label={t.results}>{matches.map((command, i) => <li key={command.href} role="presentation"><button type="button" role="option" id={`${id}-option-${i}`} tabIndex={-1} aria-selected={i === active} onMouseEnter={() => setActive(i)} onClick={() => choose(command)}><span>{command.label}</span><span className="command-path">{command.href}</span></button></li>)}</ul>
      {!matches.length && <div className="command-empty" role="status"><p>{t.noCommands}</p><button type="button" onClick={() => { setQuery(""); setActive(0); input.current?.focus(); }}>{t.changeSearch}</button></div>}
      <p id={`${id}-help`} className="muted">{t.commandHelp}</p>
    </dialog>
  </>;
}
