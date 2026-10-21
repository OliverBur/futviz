"""Helpers de maquetado compartidos por los análisis de Machine Learning.

Un análisis largo (`ArticlePage`) lleva la prosa en columna angosta y los
gráficos, tablas y llamados a todo el ancho. Esas piezas son las mismas para
cualquier artículo de la sección, así que viven acá y cada módulo
(`ml_xg.py`, y los que vengan) las importa.
"""

from viz_theme import FUENTE_FBREF, plot_html

SECTION = "Machine Learning"


def _prose(html):
    return f'<div class="wrap">{html}</div>'


def _heading(step, title, anchor):
    return (f'<div class="wrap"><h2 id="{anchor}">'
            f'<span class="step">{step}</span>{title}</h2></div>')


def _figure(fig, caption, width=880, height=560, fuente=FUENTE_FBREF):
    """El default es FBref por herencia del primer análisis; los que salen del
    detalle de tiros o de las alineaciones pasan Understat (ver el envoltorio
    `_figure` de `ml_xg.py`)."""
    return (f'<figure class="wrap-wide"><div class="chart-scroll">'
            f'{plot_html(fig, width=width, height=height, fuente=fuente)}</div>'
            f'<figcaption>{caption}</figcaption></figure>')


def _callout(title, html, warn=False):
    cls = "callout warn" if warn else "callout"
    return (f'<div class="wrap"><div class="{cls}">'
            f'<div class="callout-title">{title}</div>{html}</div></div>')


def _stat(value, label):
    return (f'<div class="wrap"><div class="stat"><div class="stat-value">{value}</div>'
            f'<div class="stat-label">{label}</div></div></div>')


def _table(headers, rows, wide=False):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(
            f'<td class="num">{c}</td>' if isinstance(c, (int, float)) else f"<td>{c}</td>"
            for c in row
        ) + "</tr>"
        for row in rows
    )
    wrap = "wrap-wide" if wide else "wrap"
    return (f'<div class="{wrap}"><div class="table-scroll"><table>'
            f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>")
