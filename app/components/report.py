"""Relatório do local para descarregar: uma página HTML que se imprime ou envia.

Tudo o que aparece vem dos resultados já calculados; nenhum texto é gerado por um modelo
de linguagem. O ficheiro não tem dependências externas e abre em qualquer navegador.
"""

from __future__ import annotations

from datetime import date
from html import escape

STYLE = """
body{font:16px/1.5 system-ui,Segoe UI,Arial,sans-serif;color:#1a1a19;max-width:820px;
margin:32px auto;padding:0 20px}
h1{font-size:26px;margin:0 0 4px} h2{font-size:19px;margin:28px 0 8px;
border-bottom:2px solid #2E7D32;padding-bottom:4px}
.sub{color:#5f5e59;margin:0 0 20px} .plan{font-size:22px;font-weight:700;margin:8px 0}
table{border-collapse:collapse;width:100%;margin:8px 0} th,td{text-align:left;padding:6px 8px;
border-bottom:1px solid #dddcd6;font-size:14.5px} th{background:#f3f2ee}
td.n,th.n{text-align:right} .note{color:#5f5e59;font-size:13.5px}
.box{background:#f3f7f3;border-left:4px solid #2E7D32;padding:10px 14px;margin:10px 0}
@media print{body{margin:10mm}}
"""


def _rows(cells: list[list[str]], numeric_from: int = 1) -> str:
    out = []
    for row in cells:
        tds = "".join(
            f'<td class="{"n" if index >= numeric_from else ""}">{escape(str(value))}</td>'
            for index, value in enumerate(row))
        out.append(f"<tr>{tds}</tr>")
    return "".join(out)


def build_report(place: str, lat: float, lon: float, summary: dict, result, names: dict,
                 recent: dict | None, window: dict, current: str, source: str,
                 today: date | None = None) -> str:
    """Devolve o relatório completo em HTML."""
    today = today or date.today()
    best = result.strategy("recomendada")

    def ok(item) -> float:
        return 10 * (1 - sum(item.raw["p_stress"]) / len(item.raw["p_stress"]))

    crops = sorted(result.crop_stats.items(), key=lambda pair: pair[1]["p_stress"])
    crop_rows = _rows([[names[key], f"{10 * (1 - item['p_stress']):.0f} em 10",
                        f"{10 * item['p_failure']:.0f} em 10", f"{item['wrsi_p10']:.0f}%",
                        f"{item['wrsi_median']:.0f}%", f"{item['wrsi_p90']:.0f}%"]
                       for key, item in crops])
    labels = {"monocultura": "Só a cultura de hoje", "convencional": "Alternar com outro cereal",
              "com_leguminosa": "Alternar com leguminosa", "recomendada": "Plano recomendado"}
    plan_rows = _rows([[labels[item.label], " → ".join(item.raw["names"]),
                        f"{ok(item):.1f} em 10", f"{100 * sum(item.raw['y_rel']) / 3:.0f}%"]
                       for item in result.strategies], numeric_from=2)
    window_rows = _rows([[label, f"{10 * (1 - item['p_stress']):.0f} em 10",
                          f"{10 * item['p_failure']:.0f} em 10"]
                         for label, item in window.items()])
    now = ""
    if recent:
        soil = "—" if recent["soil_root"] is None else f"{100 * recent['soil_root']:.0f}%"
        wind = "—" if recent["wind_kmh"] is None else f"{recent['wind_kmh']:.0f} km/h"
        now = f"""<h2>Condições recentes</h2>
<table><tr><th>Chuva nos últimos 30 dias</th><th>Temperatura máxima</th>
<th>Humidade do solo (raízes)</th><th>Vento</th></tr>
<tr><td>{recent['rain_30d_mm']:.0f} mm</td><td>{recent['tmax_c']:.1f} °C</td>
<td>{soil}</td><td>{wind}</td></tr></table>
<p class="note">Média dos últimos 7 dias com dados, até {escape(recent['last_date'])}.
Valores modelados do NASA POWER, não medições no terreno.</p>"""
    why = "".join(f"<li>{escape(line)}</li>" for line in result.explanation)
    flags = "".join(f"<li>{escape(flag)}</li>" for flag in result.flags)
    return f"""<!doctype html><html lang="pt"><head><meta charset="utf-8">
<title>Machamba Shift · {escape(place)}</title><style>{STYLE}</style></head><body>
<h1>{escape(place)}: o que plantar nas próximas três campanhas</h1>
<p class="sub">Relatório Machamba Shift · {lat:.2f}, {lon:.2f} · gerado a
{today.strftime('%d/%m/%Y')} · {result.seasons} campanhas reais analisadas</p>

<h2>Plano recomendado</h2>
<p class="plan">{escape(' → '.join(best.raw['names']))}</p>
<div class="box">Se as próximas campanhas forem como as {result.seasons} analisadas, este é o
plano que mais vezes se sai bem. Isto não é uma previsão: ninguém sabe se o próximo ano será
seco ou chuvoso.</div>
<ul>{why}</ul>
<table><tr><th>Estratégia</th><th>Plano</th><th class="n">Campanhas com água suficiente</th>
<th class="n">Colheita face ao máximo</th></tr>{plan_rows}</table>

<h2>Como é a chuva aqui</h2>
<table><tr><th>Campanha normal</th><th>Campanha má (1 em 10)</th><th>Campanha boa (1 em 10)</th>
</tr><tr><td>{summary['rain_median_mm']:.0f} mm</td><td>{summary['rain_p10_mm']:.0f} mm</td>
<td>{summary['rain_p90_mm']:.0f} mm</td></tr></table>
<p class="note">Chuva de Outubro a Abril, campanhas de {summary['first_season']} a
{summary['last_season'] + 1}.</p>
{now}
<h2>Que culturas aguentam melhor este clima</h2>
<table><tr><th>Cultura</th><th class="n">Água suficiente</th><th class="n">Falha grave</th>
<th class="n">Ano mau</th><th class="n">Ano normal</th><th class="n">Ano bom</th></tr>
{crop_rows}</table>
<p class="note">Água suficiente: a chuva cobriu pelo menos 80% do que a cultura precisava.
Falha grave: cobriu menos de metade. As três últimas colunas mostram quanto da água necessária
a chuva cobriu.</p>

<h2>Quando semear {escape(names[current].lower())}</h2>
<table><tr><th>Data de sementeira</th><th class="n">Água suficiente</th>
<th class="n">Falha grave</th></tr>{window_rows}</table>

<h2>O que este relatório não sabe</h2>
<ul>{flags}<li>Não prevê a próxima campanha: descreve o que aconteceu nas campanhas passadas.</li>
<li>Caracteriza uma zona de cerca de 50 km, não o talhão. Não substitui a análise de solo nem
o conselho do extensionista.</li></ul>
<p class="note">Clima: {escape(source)} (valores modelados). Culturas: FAO-56 e Peoples et al.
2021. Cálculos: balanço hídrico diário do solo em cada campanha real. São estimativas para
comparar opções, não previsões de colheita.</p>
</body></html>"""


NAVY, CYAN, YELLOW = "#0b1c3a", "#0e7490", "#facc15"
RISK_COLORS = ("#1baf7a", "#eda100", "#d03b3b")


def _plain(text: object) -> str:
    """Texto que as letras-padrão do PDF conseguem escrever (sem setas nem índices)."""
    return str(text).replace("→", "›").replace("₀", "0").replace("≥", ">=")


def build_pdf(place: str, lat: float, lon: float, summary: dict, result, names: dict,
              recent: dict | None, window: dict, current: str, source: str,
              today: date | None = None) -> bytes:
    """O mesmo relatório em PDF (A4), pronto a imprimir ou anexar."""
    from io import BytesIO

    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    today = today or date.today()
    best = result.strategy("recomendada")
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14,
                          textColor=colors.HexColor("#1a1a19"))
    note = ParagraphStyle("note", parent=body, fontSize=8.5, leading=11.5,
                          textColor=colors.HexColor("#5f5e59"))
    head = ParagraphStyle("head", parent=body, fontName="Helvetica-Bold", fontSize=12.5,
                          leading=16, spaceBefore=12, spaceAfter=5,
                          textColor=colors.HexColor(NAVY))
    plan = ParagraphStyle("plan", parent=body, fontName="Helvetica-Bold", fontSize=17,
                          leading=22, textColor=colors.HexColor(NAVY))
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=11.5)

    def table(header: list[str], rows: list[list[object]], widths: list[float]) -> Table:
        data = [[Paragraph(f"<b>{escape(_plain(item))}</b>", cell) for item in header]]
        data += [[item if isinstance(item, Drawing) else Paragraph(escape(_plain(item)), cell)
                  for item in row] for row in rows]
        grid = Table(data, colWidths=[width * mm for width in widths], repeatRows=1)
        grid.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef6")),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd6e0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return grid

    def risk_bar(p_stress: float, p_failure: float, width: float = 62 * mm) -> Drawing:
        parts = (1 - p_stress, p_stress - p_failure, p_failure)
        drawing, x = Drawing(width, 11), 0.0
        for share, color in zip(parts, RISK_COLORS, strict=True):
            if share > 0:
                drawing.add(Rect(x, 1, share * width, 9, fillColor=colors.HexColor(color),
                                 strokeColor=colors.white, strokeWidth=0.8))
                if share >= 0.1:
                    drawing.add(String(x + share * width / 2, 3.2, f"{10 * share:.0f}",
                                       fontName="Helvetica-Bold", fontSize=7,
                                       textAnchor="middle"))
            x += share * width
        return drawing

    def ok(item) -> float:
        return 10 * (1 - sum(item.raw["p_stress"]) / len(item.raw["p_stress"]))

    def banner(canvas, document) -> None:
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(NAVY))
        canvas.rect(0, height - 24 * mm, width, 24 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor(YELLOW))
        canvas.rect(0, height - 25 * mm, width, 1 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 15)
        canvas.drawString(18 * mm, height - 13 * mm, "MACHAMBA SHIFT")
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 9)
        canvas.drawString(18 * mm, height - 19 * mm,
                          _plain(f"{place} · {lat:.2f}, {lon:.2f} · {today.strftime('%d/%m/%Y')}"
                                 f" · {result.seasons} campanhas reais analisadas"))
        canvas.drawRightString(width - 18 * mm, height - 13 * mm,
                               "NASA Space Apps Challenge 2026 · Field Shift")
        canvas.setFillColor(colors.HexColor("#5f5e59"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 10 * mm, _plain(f"Clima: {source} (valores modelados). "
                                                   "Estimativas para comparar opções, não "
                                                   "previsões de colheita."))
        canvas.drawRightString(width - 18 * mm, 10 * mm, f"Página {document.page}")
        canvas.restoreState()

    labels = {"monocultura": "Só a cultura de hoje", "convencional": "Alternar com outro cereal",
              "com_leguminosa": "Alternar com leguminosa", "recomendada": "Plano recomendado"}
    story = [
        Paragraph("Plano recomendado para três campanhas", head),
        Paragraph(escape(_plain(" → ".join(best.raw["names"]))), plan), Spacer(1, 4),
        Paragraph(f"Se as próximas campanhas forem como as {result.seasons} analisadas, este "
                  "é o plano que mais vezes se sai bem. Não é uma previsão: ninguém sabe se o "
                  "próximo ano será seco ou chuvoso.", body), Spacer(1, 3)]
    story += [Paragraph("• " + escape(_plain(line)), body) for line in result.explanation]
    story += [Spacer(1, 6), table(
        ["Estratégia", "Plano", "Água suficiente", "Colheita face ao máximo"],
        [[labels[item.label], " → ".join(item.raw["names"]), f"{ok(item):.1f} em 10",
          f"{100 * sum(item.raw['y_rel']) / 3:.0f}%"] for item in result.strategies],
        [42, 74, 28, 30])]
    story += [Paragraph("Como é a chuva aqui (Outubro a Abril)", head), table(
        ["Campanha normal", "Campanha má (1 em 10)", "Campanha boa (1 em 10)"],
        [[f"{summary['rain_median_mm']:.0f} mm", f"{summary['rain_p10_mm']:.0f} mm",
          f"{summary['rain_p90_mm']:.0f} mm"]], [58, 58, 58])]
    if recent:
        soil = "—" if recent["soil_root"] is None else f"{100 * recent['soil_root']:.0f}%"
        wind = "—" if recent["wind_kmh"] is None else f"{recent['wind_kmh']:.0f} km/h"
        story += [Paragraph(f"Condições recentes (até {recent['last_date']})", head), table(
            ["Chuva, 30 dias", "Temperatura máxima", "Humidade do solo (raízes)", "Vento"],
            [[f"{recent['rain_30d_mm']:.0f} mm", f"{recent['tmax_c']:.1f} °C", soil, wind]],
            [43.5, 43.5, 43.5, 43.5])]
    crops = sorted(result.crop_stats.items(), key=lambda pair: pair[1]["p_stress"])
    story += [Paragraph("Que culturas aguentam melhor este clima", head), table(
        ["Cultura", "Em cada 10 campanhas", "Ano mau", "Normal", "Ano bom"],
        [[names[key], risk_bar(item["p_stress"], item["p_failure"]),
          f"{item['wrsi_p10']:.0f}%", f"{item['wrsi_median']:.0f}%", f"{item['wrsi_p90']:.0f}%"]
         for key, item in crops], [40, 68, 22, 22, 22]),
        Paragraph("Verde: a chuva cobriu pelo menos 80% da água de que a cultura precisava. "
                  "Amarelo: faltou água. Vermelho: cobriu menos de metade (falha grave). As "
                  "três últimas colunas mostram a parte da água necessária que a chuva cobriu.",
                  note)]
    story += [Paragraph(f"Quando semear {escape(names[current].lower())}", head), table(
        ["Data de sementeira", "Em cada 10 campanhas", "Falha grave"],
        [[label, risk_bar(item["p_stress"], item["p_failure"]),
          f"{10 * item['p_failure']:.0f} em 10"] for label, item in window.items()],
        [50, 74, 50])]
    limits = [*result.flags,
              "Não prevê a próxima campanha: descreve o que aconteceu nas campanhas passadas.",
              "Caracteriza uma zona de cerca de 50 km, não o talhão. Não substitui a análise "
              "de solo nem o conselho do extensionista."]
    story += [Paragraph("O que este relatório não sabe", head)]
    story += [Paragraph("• " + escape(_plain(line)), body) for line in limits]
    story += [Spacer(1, 6), Paragraph(
        "Culturas: FAO-56 e Peoples et al. 2021. Cálculos: balanço hídrico diário do solo em "
        "cada campanha real.", note)]
    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=31 * mm, bottomMargin=17 * mm,
                      title=_plain(f"Machamba Shift · {place}"),
                      author="Machamba Shift").build(story, onFirstPage=banner,
                                                     onLaterPages=banner)
    return buffer.getvalue()
