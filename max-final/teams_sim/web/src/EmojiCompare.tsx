// Design comparison: open-source emoji sets for the simulator and card icons (images load from the jsDelivr CDN).
import { Text, makeStyles, tokens } from "@fluentui/react-components";

interface E { ch: string; name: string; fluent: string; skin?: boolean; cp: string; use: string }

const EMOJI: E[] = [
  { ch: "✅", name: "Done", fluent: "Check mark button", cp: "2705", use: "signpost" },
  { ch: "⚠️", name: "Needs attention", fluent: "Warning", cp: "26a0", use: "signpost" },
  { ch: "📌", name: "Decision", fluent: "Pushpin", cp: "1f4cc", use: "signpost" },
  { ch: "📅", name: "Date / meeting", fluent: "Calendar", cp: "1f4c5", use: "signpost" },
  { ch: "⏰", name: "Reminder", fluent: "Alarm clock", cp: "23f0", use: "signpost" },
  { ch: "🔍", name: "Not found", fluent: "Magnifying glass tilted left", cp: "1f50d", use: "signpost" },
  { ch: "📎", name: "Sources", fluent: "Paperclip", cp: "1f4ce", use: "signpost" },
  { ch: "👋", name: "Greeting", fluent: "Waving hand", skin: true, cp: "1f44b", use: "signpost" },
  { ch: "👍", name: "Like", fluent: "Thumbs up", skin: true, cp: "1f44d", use: "reaction" },
  { ch: "❤️", name: "Heart", fluent: "Red heart", cp: "2764", use: "reaction" },
  { ch: "😆", name: "Laugh", fluent: "Grinning squinting face", cp: "1f606", use: "reaction" },
  { ch: "😮", name: "Surprised", fluent: "Face with open mouth", cp: "1f62e", use: "reaction" },
  { ch: "🙂", name: "Smile", fluent: "Slightly smiling face", cp: "1f642", use: "chat" },
  { ch: "🙌", name: "Celebrate", fluent: "Raising hands", skin: true, cp: "1f64c", use: "chat" },
];

const enc = (s: string) => encodeURIComponent(s);
const snake = (s: string) => s.toLowerCase().replace(/ /g, "_");
const FLUENT = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets";
const fluent3d = (e: E) => e.skin
  ? `${FLUENT}/${enc(e.fluent)}/Default/3D/${snake(e.fluent)}_3d_default.png`
  : `${FLUENT}/${enc(e.fluent)}/3D/${snake(e.fluent)}_3d.png`;
const fluentFlat = (e: E) => e.skin
  ? `${FLUENT}/${enc(e.fluent)}/Default/Flat/${snake(e.fluent)}_flat_default.svg`
  : `${FLUENT}/${enc(e.fluent)}/Flat/${snake(e.fluent)}_flat.svg`;
const NOTO_FE0F = new Set(["26a0", "2764"]);
const noto = (e: E) => `https://fonts.gstatic.com/s/e/notoemoji/latest/${e.cp}${NOTO_FE0F.has(e.cp) ? "_fe0f" : ""}/emoji.svg`;
const twemoji = (e: E) => `https://cdn.jsdelivr.net/gh/jdecked/twemoji@v15.1.0/assets/72x72/${e.cp}.png`;

const SETS: { key: string; name: string; licence: string; src?: (e: E) => string; note: string }[] = [
  { key: "f3d", name: "Fluent Emoji 3D", licence: "Microsoft · MIT", src: fluent3d, note: "What Teams shows · recommended" },
  { key: "fflat", name: "Fluent Emoji Flat", licence: "Microsoft · MIT", src: fluentFlat, note: "Same set, flat style" },
  { key: "noto", name: "Noto Color Emoji", licence: "Google · OFL", src: noto, note: "Android / Google style" },
  { key: "tw", name: "Twemoji", licence: "CC-BY 4.0 (credit)", src: twemoji, note: "Flat, simple" },
  { key: "win", name: "Windows (now in the simulator)", licence: "system font", note: "Segoe UI Emoji" },
];

const useStyles = makeStyles({
  page: { flex: 1, overflowY: "auto", padding: "24px 28px 40px", backgroundColor: tokens.colorNeutralBackground3 },
  inner: { maxWidth: "1240px", margin: "0 auto" },
  card: { backgroundColor: tokens.colorNeutralBackground1, borderRadius: tokens.borderRadiusXLarge, boxShadow: tokens.shadow4, padding: "8px 0", marginTop: "16px", overflowX: "auto" },
  table: { borderCollapse: "collapse", width: "100%" },
  th: { textAlign: "center", padding: "12px 8px", verticalAlign: "bottom", borderBottom: `1px solid ${tokens.colorNeutralStroke2}` },
  td: { textAlign: "center", padding: "8px", borderBottom: `1px solid ${tokens.colorNeutralStroke3}` },
  first: { textAlign: "left", paddingLeft: "20px", width: "200px" },
  rec: { backgroundColor: tokens.colorBrandBackground2 },
  img: { width: "40px", height: "40px", objectFit: "contain" },
  native: { fontSize: "34px", lineHeight: "40px" },
});

export function EmojiCompare() {
  const s = useStyles();
  return (
    <div className={s.page}>
      <div className={s.inner}>
        <Text size={600} weight="bold" block>Emoji sets (open source)</Text>
        <Text style={{ color: tokens.colorNeutralForeground3 }}>
          Max's 8 signposts + common reactions. Apple's iOS emoji are not open source, so they can't be used.
          In real Teams, Teams draws message emoji itself (Fluent style); this choice is for the simulator and card icons.
        </Text>
        <div className={s.card}>
          <table className={s.table}>
            <thead>
              <tr>
                <th className={`${s.th} ${s.first}`}><Text weight="semibold">Emoji</Text></th>
                {SETS.map((set) => (
                  <th key={set.key} className={`${s.th} ${set.key === "f3d" ? s.rec : ""}`}>
                    <Text weight="semibold" block>{set.name}</Text>
                    <Text size={200} block style={{ color: tokens.colorNeutralForeground3 }}>{set.licence}</Text>
                    <Text size={200} block style={{ color: set.key === "f3d" ? tokens.colorBrandForeground1 : tokens.colorNeutralForeground3 }}>{set.note}</Text>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {EMOJI.map((e) => (
                <tr key={e.cp}>
                  <td className={`${s.td} ${s.first}`}>
                    <Text weight="semibold" block>{e.name}</Text>
                    <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{e.use}</Text>
                  </td>
                  {SETS.map((set) => (
                    <td key={set.key} className={`${s.td} ${set.key === "f3d" ? s.rec : ""}`}>
                      {set.src ? <img className={s.img} src={set.src(e)} alt={e.name} loading="eager" /> : <span className={s.native}>{e.ch}</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
