"use client";
import { Component, type ReactNode } from "react";
import type { Lang } from "../../lib/ownerText";
import { WORKBENCH } from "../../lib/workbenchText";

export class ViewState extends Component<{ children: ReactNode; lang?: Lang }, { ready: boolean; error: boolean; attempt: number }> {
  state = { ready: false, error: false, attempt: 0 };
  componentDidMount() { this.setState({ ready: true }); }
  static getDerivedStateFromError() { return { error: true }; }
  render() {
    const t = WORKBENCH[this.props.lang ?? "en"];
    if (this.state.error) return <section className="panel empty" role="alert"><h2>{t.error}</h2><button type="button" onClick={() => this.setState(s => ({ error: false, attempt: s.attempt + 1 }))}>{t.retry}</button></section>;
    if (!this.state.ready) return <section className="workspace-skeleton" role="status" aria-busy="true"><p>{t.loading}</p><div className="skeleton-title" aria-hidden="true" /><div className="summary" aria-hidden="true">{[0, 1, 2].map(i => <div className="tile skeleton-tile" key={i} />)}</div><div className="skeleton-panel" aria-hidden="true" /></section>;
    return <div key={this.state.attempt}>{this.props.children}</div>;
  }
}
