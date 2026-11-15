import { ReactNode } from "react";
import Icon, { IconName } from "./Icon";

export default function Card({ icon, title, children, wide = false }: {
  icon: IconName; title: string; children: ReactNode; wide?: boolean;
}) {
  return (
    <section className={`card${wide ? " wide" : ""}`}>
      <h2 className="card-title"><Icon name={icon} />{title}</h2>
      {children}
    </section>
  );
}
