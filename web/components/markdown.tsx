import { Fragment } from "react";

// Rendu Markdown minimal et sûr (pas de HTML brut) pour les réponses de Magellan :
// gras, code inline, listes à puces, listes numérotées, titres, paragraphes.

function inline(text: string, base: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (!p) return null;
    const key = `${base}-${i}`;
    if (p.startsWith("**") && p.endsWith("**"))
      return <strong key={key}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`"))
      return (
        <code key={key} className="rounded bg-slate-200 px-1 text-[0.85em]">
          {p.slice(1, -1)}
        </code>
      );
    return <Fragment key={key}>{p}</Fragment>;
  });
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;
  const isBullet = (s: string) => /^\s*[-*•]\s+/.test(s);
  const isNum = (s: string) => /^\s*\d+\.\s+/.test(s);

  while (i < lines.length) {
    const line = lines[i];

    if (isBullet(line)) {
      const items: string[] = [];
      while (i < lines.length && isBullet(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*•]\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-1 list-disc space-y-0.5 pl-5">
          {items.map((it, j) => (
            <li key={j}>{inline(it, `${key}-${j}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (isNum(line)) {
      const items: string[] = [];
      while (i < lines.length && isNum(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push(
        <ol key={key++} className="my-1 list-decimal space-y-0.5 pl-5">
          {items.map((it, j) => (
            <li key={j}>{inline(it, `${key}-${j}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    if (line.trim() === "") {
      i++;
      continue;
    }

    if (/^#{1,6}\s+/.test(line)) {
      blocks.push(
        <p key={key++} className="font-semibold">
          {inline(line.replace(/^#{1,6}\s+/, ""), `${key}`)}
        </p>,
      );
      i++;
      continue;
    }

    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !isBullet(lines[i]) &&
      !isNum(lines[i]) &&
      !/^#{1,6}\s+/.test(lines[i])
    ) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++}>
        {para.map((pl, j) => (
          <Fragment key={j}>
            {inline(pl, `${key}-${j}`)}
            {j < para.length - 1 ? <br /> : null}
          </Fragment>
        ))}
      </p>,
    );
  }

  return <div className="space-y-1.5">{blocks}</div>;
}
