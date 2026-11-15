/** How the app works: what Spotify and YouTube allow, why so much has to be set up and what the listening
 * statistics can and cannot know, a card for each topic with what happens, why and what to do. */

import { useEffect, useState } from "react";
import { get } from "../api";
import Card from "../components/Card";
import { IconName } from "../components/Icon";

interface HelpData {
  title: string;
  lead: string;
  topics: { icon: IconName; title: string; why: string; todo: string }[];
}

export default function Help() {
  const [data, setData] = useState<HelpData | null>(null);
  useEffect(() => {
    get<HelpData>("/api/help").then(setData, () => {});
  }, []);
  if (!data) return null;
  return (
    <div className="page">
      <header className="toolbar"><h1 className="period-title">{data.title}</h1></header>
      <p className="lead muted">{data.lead}</p>
      <div className="overview help">
        {data.topics.map((topic) => (
          <Card key={topic.title} icon={topic.icon} title={topic.title}>
            <p>{topic.why}</p>
            {topic.todo && <p className="muted">{topic.todo}</p>}
          </Card>
        ))}
      </div>
    </div>
  );
}
