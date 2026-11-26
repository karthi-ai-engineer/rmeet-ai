import type React from "react";
// Small pieces shared by the Teams and Chat screens.
import { Button, Link, Popover, PopoverSurface, PopoverTrigger, Text, Tooltip, makeStyles, tokens } from "@fluentui/react-components";
import { Open16Regular } from "@fluentui/react-icons";
import { BACKGROUND, PEOPLE, type Source } from "./mock";

export const MAX_ORANGE = "#F7630C";

const useStyles = makeStyles({
  text: { whiteSpace: "pre-wrap", lineHeight: tokens.lineHeightBase300, marginTop: "2px" },
  cite: {
    display: "inline-flex", alignItems: "center", justifyContent: "center", minWidth: "16px", height: "16px",
    padding: "0 3px", margin: "0 1px", borderRadius: "4px", fontSize: "10px", verticalAlign: "1px",
    backgroundColor: tokens.colorNeutralBackground5, color: tokens.colorNeutralForeground2, cursor: "pointer",
  },
  sources: { marginTop: "8px", display: "flex", flexDirection: "column", gap: "2px" },
});

export function personName(id: string): string {
  if (id === "max") return "Max";
  return PEOPLE.find((p) => p.id === id)?.name ?? BACKGROUND[id] ?? id;
}

export function MaxAvatar({ size = 32 }: { size?: number }) {
  return (
    <span
      aria-label="Max"
      style={{
        width: size, height: size, borderRadius: "50%", background: MAX_ORANGE, color: "#fff", flexShrink: 0,
        display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.55,
      }}
    >
      ☁
    </span>
  );
}

/** Message text: **bold** and [n] citation markers. */
const DEMO_CITE = typeof window !== "undefined" && new URLSearchParams(window.location.search).get("demo") === "cite";

/** A [n] source chip; with sources it opens a small card (title, where, open) like Teams citations. */
function Cite({ n, sources, first }: { n: string; sources?: Source[]; first: boolean }) {
  const s = useStyles();
  const src = sources?.find((x) => String(x.n) === n);
  if (!src) return <Tooltip content={`Source ${n}`} relationship="label"><span className={s.cite}>{n}</span></Tooltip>;
  return (
    <Popover openOnHover withArrow positioning="above" defaultOpen={DEMO_CITE && first}>
      <PopoverTrigger disableButtonEnhancement><span className={s.cite} role="button" tabIndex={0}>{n}</span></PopoverTrigger>
      <PopoverSurface style={{ maxWidth: 320, padding: "12px 14px" }}>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }} block>Source {n}</Text>
        <Text weight="semibold" block>{src.title}</Text>
        <Text size={200} block style={{ margin: "4px 0 8px" }}>{src.where}</Text>
        <Button size="small" icon={<Open16Regular />}>Open at this spot</Button>
      </PopoverSurface>
    </Popover>
  );
}

export function RichText({ text, after, sources }: { text: string; after?: React.ReactNode; sources?: Source[] }) {
  let citeCount = 0;
  const s = useStyles();
  const parts = text.replace(/ \[(\d+)\]/g, "\u00a0[$1]").split(/(\*\*[^*]+\*\*|\S+\u00a0\[\d+\][.,;:]?|\[\d+\][.,;:]?)/g);
  return (
    <div className={s.text}>
      {parts.map((p, i) => {
        if (p.startsWith("**")) return <b key={i}>{p.slice(2, -2)}</b>;
        const m = p.match(/^(\S*?)\u00a0?\[(\d+)\]([.,;:]?)$/);
        if (m) {
          // keep the word before, the source chip and the punctuation together (no lonely chip or "." on a new line)
          return (
            <span key={i} style={{ whiteSpace: "nowrap" }}>
              {m[1] && <>{m[1].startsWith("**") ? <b>{m[1].slice(2, -2)}</b> : m[1]}{" "}</>}
              <Cite n={m[2]} sources={sources} first={citeCount++ === 0} />
              {m[3]}
            </span>
          );
        }
        return <span key={i}>{p}</span>;
      })}
      {after}
    </div>
  );
}

export function Sources({ sources }: { sources: Source[] }) {
  const s = useStyles();
  return (
    <div className={s.sources}>
      {sources.map((src) => (
        <Text key={src.n} size={200}>
          <span className={s.cite}>{src.n}</span> <Link>{src.title}</Link>{" "}
          <span style={{ color: tokens.colorNeutralForeground3 }}>· {src.where}</span>
        </Text>
      ))}
    </div>
  );
}
