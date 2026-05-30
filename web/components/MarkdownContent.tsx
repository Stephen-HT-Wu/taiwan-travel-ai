import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./Chat.module.css";
import { linkPlaceNames } from "./linkPlaceNames";
import { resolvePlaceByLink, type MapPlace } from "./mapTypes";

type MarkdownContentProps = {
  content: string;
  places?: MapPlace[];
  mapPlaces?: MapPlace[];
  selectedPlaceId?: string | null;
  onPlaceSelect?: (place: MapPlace) => void;
};

export default function MarkdownContent({
  content,
  places = [],
  mapPlaces = [],
  selectedPlaceId = null,
  onPlaceSelect,
}: MarkdownContentProps) {
  const hasPlaces = places.length > 0 || mapPlaces.length > 0;
  const markdown = hasPlaces ? linkPlaceNames(content, places, mapPlaces) : content;

  return (
    <div className={styles.markdown}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#map-")) {
              const linkId = href.slice("#map-".length);
              const label = String(children);
              const place = resolvePlaceByLink(linkId, label, places, mapPlaces);
              const activeId = place?.id ?? decodeURIComponent(linkId);
              const isActive = activeId === selectedPlaceId;

              return (
                <button
                  type="button"
                  className={`${styles.placeLink} ${isActive ? styles.placeLinkActive : ""}`}
                  data-place-id={activeId}
                  onClick={() => {
                    if (place) onPlaceSelect?.(place);
                  }}
                >
                  {children}
                </button>
              );
            }

            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
