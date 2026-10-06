// Utilidades compartidas por los tres informes (.docx) de la fase de validación.
const fs = require("fs");
const path = require("path");
const d = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const STATS = path.join(ROOT, "resultados", "02_analisis_estadistico");
const DATA = JSON.parse(fs.readFileSync(path.join(STATS, "datos_informe.json"), "utf-8"));
const S = DATA.estadistica;

const FONT = "Calibri";
const NAVY = "1F3864";
const ZEBRA = "EEF3FA";
const PAGE_W = 11906, MARGIN = 1134; // A4, 2 cm
const CONTENT_W = PAGE_W - 2 * MARGIN; // 9638 DXA

const fmt = (v, dec = 1) => (v === null || v === undefined || v === "" || Number.isNaN(v)) ? "—"
  : Number(v).toLocaleString("es-PE", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const int = (v) => fmt(v, 0);
const pct = (v, dec = 2) => `${fmt(v, dec)} %`;
const pval = (p) => (p === null || p === undefined) ? "—" : (p < 0.001 ? "< 0.001" : fmt(p, 3));

function run(text, opts = {}) { return new d.TextRun({ text: String(text), font: FONT, size: opts.size || 21, ...opts }); }
function p(content, opts = {}) {
  const children = Array.isArray(content) ? content.map((c) => typeof c === "string" ? run(c) : c) : [run(content, opts.run || {})];
  return new d.Paragraph({ children, spacing: { after: 120, line: 276 }, alignment: opts.align || d.AlignmentType.JUSTIFIED, ...opts.para });
}
const b = (t) => run(t, { bold: true });
const i = (t) => run(t, { italics: true });
function h1(t) { return new d.Paragraph({ heading: d.HeadingLevel.HEADING_1, children: [run(t, { bold: true, size: 28, color: NAVY })], spacing: { before: 280, after: 140 } }); }
function h2(t) { return new d.Paragraph({ heading: d.HeadingLevel.HEADING_2, children: [run(t, { bold: true, size: 24, color: NAVY })], spacing: { before: 220, after: 100 } }); }
function bullet(content) {
  const children = Array.isArray(content) ? content.map((c) => typeof c === "string" ? run(c) : c) : [run(content)];
  return new d.Paragraph({ children, numbering: { reference: "vinetas", level: 0 }, spacing: { after: 60, line: 264 } });
}
function caption(t) { return new d.Paragraph({ children: [run(t, { bold: true, italics: true, size: 19 })], spacing: { before: 200, after: 80 }, keepNext: true }); }
function note(t) { return new d.Paragraph({ children: [run(t, { size: 17, italics: true, color: "555555" })], spacing: { after: 200 } }); }

function cell(text, width, opts = {}) {
  return new d.TableCell({
    width: { size: width, type: d.WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: d.ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: d.VerticalAlign.CENTER,
    children: [new d.Paragraph({ alignment: opts.align || d.AlignmentType.LEFT,
      children: [run(text, { size: opts.size || 17, bold: !!opts.bold, color: opts.color })] })],
  });
}

// headers: [texto]; rows: [[...]]; weights: anchos relativos; align: 'L'|'R'|'C' por columna
function table(headers, rows, weights, align = [], size = 17) {
  const total = weights.reduce((a, c) => a + c, 0);
  const widths = weights.map((w) => Math.floor((w / total) * CONTENT_W));
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, c) => a + c, 0);
  const A = (k) => ({ R: d.AlignmentType.RIGHT, C: d.AlignmentType.CENTER }[align[k]] || d.AlignmentType.LEFT);
  const head = new d.TableRow({ tableHeader: true, children: headers.map((h, k) => cell(h, widths[k], { fill: NAVY, color: "FFFFFF", bold: true, align: A(k), size })) });
  const body = rows.map((r, ri) => new d.TableRow({ cantSplit: true,
    children: r.map((v, k) => cell(v, widths[k], { fill: ri % 2 ? ZEBRA : undefined, align: A(k), size })) }));
  return new d.Table({ width: { size: CONTENT_W, type: d.WidthType.DXA }, columnWidths: widths, rows: [head, ...body] });
}

let FIG = 0;
function figure(file, title, widthPx = 620) {
  FIG += 1;
  const full = path.join(STATS, "figuras", file);
  const buf = fs.readFileSync(full);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  return [caption(`Figura ${FIG}. ${title}`), new d.Paragraph({ alignment: d.AlignmentType.CENTER, keepNext: true, children: [new d.ImageRun({ type: "png", data: buf,
    transformation: { width: widthPx, height: Math.round(widthPx * h / w) }, altText: { title, description: title, name: file } })] }),
  note(`Fuente: resultados/02_analisis_estadistico/figuras/${file}. Elaboración propia.`)];
}

function cover(title, subtitle, fase) {
  return [
    new d.Paragraph({ spacing: { before: 2400 }, children: [] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, children: [run("Universidad Nacional Mayor de San Marcos — Facultad de Ingeniería de Sistemas", { size: 20, color: "555555" })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, spacing: { before: 600, after: 200 }, children: [run(title, { bold: true, size: 40, color: NAVY })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, spacing: { after: 400 }, children: [run(subtitle, { size: 26 })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, children: [run(fase, { size: 22, italics: true })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, spacing: { before: 1200 }, children: [run("Tesis: Diseño y prototipado de una arquitectura de referencia offline-first para la gestión logística de inventarios en empresas con operaciones en zonas de conectividad limitada: el caso de Marco Peruana", { size: 20 })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, spacing: { before: 200 }, children: [run("Autor: Príncipe Velásquez, Iván", { size: 20 })] }),
    new d.Paragraph({ alignment: d.AlignmentType.CENTER, spacing: { before: 200 }, children: [run(`Fecha de generación: ${new Date().toISOString().slice(0, 10)}`, { size: 20 })] }),
    new d.Paragraph({ children: [new d.PageBreak()] }),
  ];
}

function build(file, header, children) {
  const doc = new d.Document({
    creator: "Príncipe Velásquez, Iván", title: header,
    styles: { default: { document: { run: { font: FONT, size: 21 } } } },
    numbering: { config: [{ reference: "vinetas", levels: [{ level: 0, format: d.LevelFormat.BULLET, text: "•", alignment: d.AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
    sections: [{
      properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
      headers: { default: new d.Header({ children: [new d.Paragraph({ alignment: d.AlignmentType.RIGHT, children: [run(header, { size: 16, italics: true, color: "777777" })] })] }) },
      footers: { default: new d.Footer({ children: [new d.Paragraph({ alignment: d.AlignmentType.CENTER, children: [run("Página ", { size: 16 }), new d.TextRun({ children: [d.PageNumber.CURRENT], font: FONT, size: 16 })] })] }) },
      children,
    }],
  });
  return d.Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(file, buf); console.log("escrito", file); });
}

module.exports = { d, ROOT, STATS, DATA, S, fmt, int, pct, pval, run, p, b, i, h1, h2, bullet, caption, note, table, figure, cover, build };
