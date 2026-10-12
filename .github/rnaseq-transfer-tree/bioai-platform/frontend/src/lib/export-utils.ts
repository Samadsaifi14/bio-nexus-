import { viewerBg } from "./theme-canvas";

export function downloadTsv(headers: string[], rows: string[][], filename: string) {
  const tsv = [headers.join("\t"), ...rows.map(r => r.join("\t"))].join("\n");
  const a = document.createElement("a");
  a.download = filename;
  a.href = "data:text/tab-separated-values;charset=utf-8," + encodeURIComponent(tsv);
  a.click();
}

export function downloadText(text: string, filename: string) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = "data:text/plain;charset=utf-8," + encodeURIComponent(text);
  a.click();
}

export function downloadJson(data: unknown, filename: string) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = "data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
  a.click();
}

export function copyText(text: string, done?: () => void) {
  navigator.clipboard.writeText(text).then(done);
}

export function exportSvgPng(svgEl: SVGSVGElement | null, filename: string) {
  if (!svgEl) return;
  const svgStr = new XMLSerializer().serializeToString(svgEl);
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d")!;
  const img = new window.Image();
  img.onload = () => {
    canvas.width = img.width;
    canvas.height = img.height;
    ctx.fillStyle = viewerBg('#06060B');
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0);
    const a = document.createElement("a");
    a.download = filename;
    a.href = canvas.toDataURL("image/png");
    a.click();
  };
  img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgStr)));
}

export function downloadFasta(header: string, sequence: string, filename: string) {
  const fasta = `>${header}\n${sequence}`;
  const a = document.createElement("a");
  a.download = filename;
  a.href = "data:text/fasta;charset=utf-8," + encodeURIComponent(fasta);
  a.click();
}

export function downloadCanvasPng(canvas: HTMLCanvasElement, filename: string) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = canvas.toDataURL("image/png");
  a.click();
}
