import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { WrappedStory } from "./pages/Wrapped";
import "./styles.css";

const STORY = new URLSearchParams(location.search).get("story");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* A hidden window drawing one summary slide as a story picture (electron/main.ts storyPicture) */}
    {STORY ? <WrappedStory id={STORY} slide={Number(new URLSearchParams(location.search).get("slide") ?? 0)} /> : <App />}
  </StrictMode>,
);
