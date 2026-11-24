import { useEffect, useState } from "react";
import { imageUrl } from "../api";

/** A cover or artist photo from the backend, which looks missing ones up on Deezer; the initial without one.
 * `eager` loads at once and shows without fading in, for a picture already in the cache that moves itself.
 * `fallback` is tried when src has no picture, such as the artist's photo for a cover Deezer does not have. */
export default function Picture({ src, alt, round = false, className = "", eager = false, fallback }: {
  src: string; alt: string; round?: boolean; className?: string; eager?: boolean; fallback?: string;
}) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [second, setSecond] = useState(false);
  useEffect(() => {
    setFailed(false);
    setLoaded(false);
    setSecond(false);
  }, [src]);
  const shape = `picture ${round ? "round" : ""} ${className}`;
  if (failed) return <span className={`${shape} placeholder`}>{alt.trim().charAt(0).toUpperCase()}</span>;
  return (
    <img
      className={`${shape}${loaded && !eager ? " loaded" : ""}`}
      src={imageUrl(second && fallback ? fallback : src)}
      alt=""
      loading={eager ? "eager" : "lazy"}
      onLoad={() => setLoaded(true)}
      onError={() => (fallback && !second ? setSecond(true) : setFailed(true))}
    />
  );
}
