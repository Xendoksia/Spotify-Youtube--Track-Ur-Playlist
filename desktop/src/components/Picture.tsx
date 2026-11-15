import { useEffect, useState } from "react";
import { imageUrl } from "../api";

/** A cover or artist photo from the backend, which looks missing ones up on Deezer; the initial without one. */
export default function Picture({ src, alt, round = false, className = "" }: {
  src: string; alt: string; round?: boolean; className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    setFailed(false);
    setLoaded(false);
  }, [src]);
  const shape = `picture ${round ? "round" : ""} ${className}`;
  if (failed) return <span className={`${shape} placeholder`}>{alt.trim().charAt(0).toUpperCase()}</span>;
  return (
    <img
      className={`${shape}${loaded ? " loaded" : ""}`}
      src={imageUrl(src)}
      alt=""
      loading="lazy"
      onLoad={() => setLoaded(true)}
      onError={() => setFailed(true)}
    />
  );
}
