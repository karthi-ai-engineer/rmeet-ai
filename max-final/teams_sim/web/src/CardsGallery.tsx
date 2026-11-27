// UI design: all of Max's cards, drawn by Microsoft's Adaptive Cards renderer (the same card JSON Teams receives).
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import * as AC from "adaptivecards";
import { Badge, Text, makeStyles, shorthands, tokens } from "@fluentui/react-components";
import { CARDS, teamsHostConfig, type CardDemo } from "./cards";
import { MaxAvatar } from "./ui";
import { MOMENTS, MaxMomentTile, type MaxMoment } from "./avatar/MaxMoment";

// Simple markdown for card text (Teams supports a small subset: bold, lists, line breaks).
AC.AdaptiveCard.onProcessMarkdown = (text, result) => {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  result.outputHtml = esc
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .split("\n")
    .map((l) => (l.startsWith("- ") ? `• ${l.slice(2)}` : l))
    .join("<br/>");
  result.didProcess = true;
};

const useStyles = makeStyles({
  page: { flex: 1, overflowY: "auto", padding: "24px 28px 40px", backgroundColor: tokens.colorNeutralBackground3 },
  inner: { maxWidth: "1240px", margin: "0 auto" },
  head: { marginBottom: "18px" },
  item: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "18px 20px", marginBottom: "18px" },
  itemHead: { display: "flex", alignItems: "baseline", gap: "10px", flexWrap: "wrap", marginBottom: "12px" },
  pair: { display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: "20px", alignItems: "start" },
  label: { fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold, marginBottom: "6px", display: "block" },
  msg: { display: "flex", gap: "10px" },
  msgMeta: { display: "flex", gap: "8px", alignItems: "baseline", marginBottom: "4px" },
  frame: {
    borderRadius: tokens.borderRadiusLarge, border: `1px solid ${tokens.colorNeutralStroke2}`, overflow: "hidden", maxWidth: "520px",
    "& .ac-adaptiveCard": { borderRadius: tokens.borderRadiusLarge },
    "& .ac-pushButton": {
      fontFamily: tokens.fontFamilyBase, fontSize: tokens.fontSizeBase300, fontWeight: tokens.fontWeightSemibold, padding: "5px 14px",
      borderRadius: tokens.borderRadiusMedium, border: `1px solid ${tokens.colorNeutralStroke1}`, cursor: "pointer",
      backgroundColor: tokens.colorNeutralBackground1, color: tokens.colorNeutralForeground1, minHeight: "32px",
    },
    "& .ac-pushButton:hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
    "& .ac-pushButton.style-positive, & .ac-pushButton.primary": {
      backgroundColor: tokens.colorBrandBackground, color: tokens.colorNeutralForegroundOnBrand, ...shorthands.borderColor(tokens.colorBrandBackground),
    },
    "& .ac-pushButton.expanded": { backgroundColor: tokens.colorNeutralBackground1Selected },
    "& .ac-input, & .ac-textInput": {
      fontFamily: tokens.fontFamilyBase, fontSize: tokens.fontSizeBase300, padding: "6px 8px", borderRadius: tokens.borderRadiusMedium,
      border: `1px solid ${tokens.colorNeutralStroke1}`, backgroundColor: tokens.colorNeutralBackground1, color: tokens.colorNeutralForeground1, width: "100%", boxSizing: "border-box",
    },
  },
  toast: { marginTop: "8px", fontSize: tokens.fontSizeBase200, color: tokens.colorNeutralForeground3 },
});

// In the simulator, Max's tile images (id "maxTile-<moment>") are drawn by the live character instead of the GIF/PNG.
const BLANK = "data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==";
function simTiles(node: unknown): unknown {
  if (Array.isArray(node)) return node.map(simTiles);
  if (node && typeof node === "object") {
    const o = node as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const k in o) out[k] = simTiles(o[k]);
    if (o.type === "Image" && typeof o.id === "string" && o.id.startsWith("maxTile-")) out.url = BLANK; // no request to the (real) image URL
    return out;
  }
  return node;
}

export function RenderedCard({ json, dark, onAction }: { json: object; dark: boolean; onAction?: (verb: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const actionRef = useRef(onAction);
  actionRef.current = onAction;
  const [tiles, setTiles] = useState<{ el: HTMLElement; moment: MaxMoment; size: number }[]>([]);
  useEffect(() => {
    const ac = new AC.AdaptiveCard();
    ac.hostConfig = new AC.HostConfig(teamsHostConfig(dark));
    ac.onExecuteAction = (action) => {
      const verb = action instanceof AC.ExecuteAction ? action.verb ?? action.title ?? "" : action.title ?? "";
      actionRef.current?.(verb);
    };
    ac.parse(simTiles(json));
    const el = ac.render();
    const found: { el: HTMLElement; moment: MaxMoment; size: number }[] = [];
    if (ref.current && el) {
      ref.current.innerHTML = "";
      ref.current.appendChild(el);
      el.querySelectorAll<HTMLElement>('[id^="maxTile-"]').forEach((host) => {
        const moment = host.id.slice("maxTile-".length) as MaxMoment;
        if (!(moment in MOMENTS)) return;
        const size = parseInt(host.querySelector("img")?.style.width ?? "", 10) || 96;
        host.innerHTML = "";
        const mount = document.createElement("div");
        host.appendChild(mount);
        found.push({ el: mount, moment, size });
      });
    }
    setTiles(found);
  }, [json, dark]);
  return <><div ref={ref} />{tiles.map((t, i) => createPortal(<MaxMomentTile moment={t.moment} size={t.size} />, t.el, String(i)))}</>;
}

/** A card with Teams-like buttons and inputs (used in the gallery and inside chat messages). */
export function CardFrame({ json, dark, onAction }: { json: object; dark: boolean; onAction?: (verb: string) => void }) {
  const s = useStyles();
  return <div className={s.frame}><RenderedCard json={json} dark={dark} onAction={onAction} /></div>;
}

function MaxMessage({ children, time = "10:41", system }: { children: React.ReactNode; time?: string; system?: boolean }) {
  const s = useStyles();
  return (
    <div className={s.msg}>
      <MaxAvatar size={32} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className={s.msgMeta}>
          <Text weight="semibold" style={{ color: "#F7630C" }}>Max</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{time}</Text>
          {!system && <Badge appearance="tint" color="informative" size="small">AI generated</Badge>}
        </div>
        {children}
      </div>
    </div>
  );
}

function Demo({ c, dark }: { c: CardDemo; dark: boolean }) {
  const s = useStyles();
  const [clicked, setClicked] = useState<string | null>(null);
  return (
    <div className={s.item}>
      <div className={s.itemHead}>
        <Text size={500} weight="semibold">{c.name}</Text>
        <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{c.where}</Text>
      </div>
      <div className={s.pair}>
        <div>
          <span className={s.label}>As posted (buttons work: try them)</span>
          <MaxMessage system={c.system}><div className={s.frame}><RenderedCard json={c.before} dark={dark} onAction={setClicked} /></div></MaxMessage>
          {clicked && <div className={s.toast}>→ Button "{clicked}" sent to Max (Universal Action). Max checks who clicked, acts, and updates the card.</div>}
        </div>
        {c.after && (
          <div>
            <span className={s.label}>{c.afterLabel ?? "After"} (the same card, updated in place)</span>
            <MaxMessage system={c.system}><div className={s.frame}><RenderedCard json={c.after} dark={dark} /></div></MaxMessage>
          </div>
        )}
      </div>
    </div>
  );
}

export function CardsGallery({ dark, only }: { dark: boolean; only?: string[] }) {
  const s = useStyles();
  const list = only?.length ? CARDS.filter((c) => only.includes(c.id)) : CARDS;
  return (
    <div className={s.page}>
      <div className={s.inner}>
        <div className={s.head}>
          <Text size={600} weight="bold" block>Max's cards</Text>
          <Text style={{ color: tokens.colorNeutralForeground3 }}>
            Drawn by Microsoft's Adaptive Cards renderer from the same card data Teams will receive (Teams-like look; meeting cards come with Max Meeting).
          </Text>
        </div>
        {list.map((c) => <Demo key={c.id} c={c} dark={dark} />)}
      </div>
    </div>
  );
}
