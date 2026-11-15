import { ReactNode } from "react";
import Icon, { IconName } from "./Icon";

/** A bordered section of a page with an icon and a title, and a line about it under the title. */
export default function Card({ icon, title, summary, children, className = "" }: {
  icon: IconName; title: string; summary?: string; children: ReactNode; className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      <h2 className="card-title"><Icon name={icon} />{title}</h2>
      {summary && <p className="card-summary">{summary}</p>}
      {children}
    </section>
  );
}
