"""Textos de lectura de cada gráfico, **calculados desde los datos**.

Por qué existe este módulo y no un diccionario de frases escritas a mano:

1. Un insight escrito a mano es una afirmación que nadie vuelve a verificar. Al
   revisar la idea salió el ejemplo "la Bundesliga es la liga con más faltas y
   menos posesión": las dos mitades son falsas (es la que **menos** falta, 10.4
   contra 12.7 de la Serie A, y la posesión promedio de toda liga es
   mecánicamente ~50% porque suma 100% por partido).
2. Con 5 temporadas × 6 estados de filtro × 14 gráficos son cientos de frases.
   A mano no se mantienen, y quedan viejas en cuanto se rebajan los datos.

Acá cada frase se arma con los mismos `groupby` que dibujan el gráfico, así que
no pueden contradecirse. Los generadores devuelven `(fija, salta)`:

- **fija**: misma estructura siempre, con los valores del estado actual.
- **salta**: el dato más notable de ese estado, elegido por una regla (no es
  una frase fija con otro número: cambia de sujeto según qué se destaque).

Lo usan por igual `web/charts/*.py` y los notebooks de `code/`, para que el
texto del sitio y el del notebook nunca se separen.
"""

LIGA_TODAS = "__all__"


def _fmt(x, dec=2):
    return f"{x:.{dec}f}"


def _pct(a, b, dec=2):
    """Cuánto más grande es `a` que `b`, en %.

    Se calcula sobre los valores **ya redondeados a como se muestran**: si en el
    texto se lee "2.59 contra 1.76", el porcentaje tiene que ser el que sale de
    esos dos números (47%) y no el de los decimales ocultos (48%). Un lector que
    haga la cuenta tiene que llegar al mismo resultado."""
    return (round(a, dec) / round(b, dec) - 1) * 100


def _verbo(nuevo, viejo, baja, sube, igual="quedó igual", tol=0.005):
    """Verbo que corresponde a la dirección real del cambio. Tenerlo fijo en la
    plantilla es la forma más fácil de escribir una frase que se contradice a sí
    misma ("bajaron de 2.09 a 2.15")."""
    if abs(nuevo - viejo) < tol:
        return igual
    return baja if nuevo < viejo else sube


# --------------------------------------------------------------------------
# Eficiencia de definición — SoT% vs. G/SoT (un punto por equipo)
# --------------------------------------------------------------------------

X_DEF, Y_DEF = "sh_Standard_SoT%", "sh_Standard_G/SoT"


def definicion_que_mirar():
    return ("Cada punto es un equipo. El eje horizontal es **llegar** (qué "
            "porcentaje de sus tiros van a puerta) y el vertical es **definir** "
            "(cuántos goles saca de cada tiro a puerta). Arriba a la derecha "
            "están los que hacen bien las dos cosas; abajo a la derecha, los que "
            "tiran mucho a puerta y no la meten.")


def definicion_por_que(df):
    r = df[X_DEF].corr(df[Y_DEF])
    return (
        f"Las dos van en ejes separados porque **no son la misma habilidad**: "
        f"correlacionan {_fmt(r)} sobre las {len(df)} observaciones, o sea que "
        f"comparten apenas un {r ** 2 * 100:.0f}% de su variación. Un equipo puede "
        f"ser muy bueno generando remates claros y flojo rematándolos, y al revés. "
        f"Si se mezclaran en un solo indicador de \"eficiencia\" esa distinción se "
        f"perdería, que es justo lo que el gráfico quiere mostrar."
    )


def definicion(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    mejor = d.loc[d[Y_DEF].idxmax()]
    media = d[Y_DEF].mean()
    fija = (f"En {ambito}, **{mejor['Squad']}** es el que más gol saca por tiro a "
            f"puerta ({_fmt(mejor[Y_DEF])} G/SoT) contra una media de "
            f"{_fmt(media)}.")

    # El dato que salta: el equipo con mayor desajuste entre lo bien que llega
    # y lo bien que define. Se compara por percentil dentro del ámbito, no por
    # valor bruto, para que las dos métricas sean comparables entre sí.
    if len(d) < 4:
        return fija, None
    rx = d[X_DEF].rank(pct=True)
    ry = d[Y_DEF].rank(pct=True)
    brecha = rx - ry
    i_alto = brecha.idxmax()   # llega mucho, define poco
    i_bajo = brecha.idxmin()   # llega poco, define mucho

    if abs(brecha[i_alto]) >= abs(brecha[i_bajo]):
        e = d.loc[i_alto]
        salta = (f"El desajuste más grande es el de **{e['Squad']}**: está entre "
                 f"los que más tiros a puerta consiguen ({_fmt(e[X_DEF], 1)}%) pero "
                 f"de los que menos los aprovechan ({_fmt(e[Y_DEF])} G/SoT).")
    else:
        e = d.loc[i_bajo]
        salta = (f"El caso opuesto lo tiene **{e['Squad']}**: llega poco a puerta "
                 f"({_fmt(e[X_DEF], 1)}%) y aun así es de los más letales cuando "
                 f"llega ({_fmt(e[Y_DEF])} G/SoT).")
    return fija, salta


# --------------------------------------------------------------------------
# Radar de perfil de liga
# --------------------------------------------------------------------------

def radar_que_mirar():
    return ("Cada eje es una métrica y cada forma la \"personalidad\" de una liga. "
            "Lo que importa no es el tamaño total de la figura sino **dónde se "
            "abulta**: un pico en Faltas y poco en Goles describe una liga trabada; "
            "lo contrario, una de ida y vuelta.")


def radar_por_que():
    return (
        "Las 8 métricas se eligieron por **eta²** (cuánta de la variación explica la "
        "liga, frente al ruido entre equipos de una misma liga), no por criterio "
        "propio. Quedaron fuera dos que parecían obvias: **Posesión**, porque suma "
        "100% por partido y el promedio de cualquier liga es mecánicamente ~50% — es "
        "un eje muerto en cualquier normalización; y **Centros**, porque las 5 ligas "
        "hacen prácticamente los mismos (17-18 por 90'). También se descartaron "
        "Asistencias y goles recibidos por redundancia: correlacionan 0.98 con Goles "
        "y −0.84 con CS%, así que duplicaban un eje ya presente.\n\n"
        "La escala es `valor / máximo` y no min-max ni z-score. Con min-max la peor "
        "liga queda anclada en 0 y la mejor en 1 **aunque la diferencia real sea "
        "mínima**: 170 tiros contra 180 se verían como polos opuestos. Con `valor / "
        "máximo` el 0 del eje es el 0 real de la métrica y la separación refleja la "
        "proporción de verdad. El divisor es el máximo de las **25 liga-temporada**, "
        "para que las formas se puedan comparar también entre temporadas."
    )


def radar(avg, labels, season, seasons):
    """`avg` es el promedio por (temporada, liga) de las métricas del radar."""
    sub = avg.loc[season]
    sep = ((1 - sub.min() / sub.max()) * 100).sort_values(ascending=False)
    mas, menos = sep.index[0], sep.index[-1]
    fija = (f"En {season} las ligas se separan sobre todo en **{labels[mas]}** "
            f"({sep.iloc[0]:.0f}% entre la primera y la última) y casi nada en "
            f"**{labels[menos]}** ({sep.iloc[-1]:.0f}%).")

    # El dato que salta es la desviación liga-eje más marcada respecto del
    # promedio de las 5. Se eligió esto y no "qué eje es el más plano" porque lo
    # segundo da la MISMA frase en las 5 temporadas (Tiros siempre), y un texto
    # que no cambia al mover el selector no aporta nada.
    rel = sub / sub.mean() - 1
    liga_top, eje_top = rel.stack().abs().idxmax()
    valor = rel.loc[liga_top, eje_top] * 100
    lado = "por encima" if valor > 0 else "por debajo"
    salta = (f"La desviación más marcada es la de **{liga_top}** en "
             f"**{labels[eje_top]}**: un {abs(valor):.0f}% {lado} del promedio de "
             f"las 5 ligas.")
    return fija, salta


# --------------------------------------------------------------------------
# Disciplina: tarjetas amarillas por 90'
# --------------------------------------------------------------------------

COL_CRDY = "p90_CrdY"


def disciplina_que_mirar():
    return ("Cada punto es un equipo y la caja marca el rango donde cae la mitad "
            "central de la liga. Lo interesante son las dos cosas a la vez: **dónde "
            "está la caja** (qué tan tarjetera es la liga) y **qué tan alta es** "
            "(si todos sus equipos se parecen o hay de todo).")


def disciplina_por_que():
    return (
        "Van **por 90 minutos** y no en total porque la Bundesliga juega 34 jornadas "
        "y las otras cuatro 38: en bruto sus equipos parecerían más disciplinados "
        "solo por jugar menos.\n\n"
        "Vale la pena leerlo como lo que es: una amarilla necesita una falta **y** un "
        "árbitro que la sancione. Cuando una liga entera se mueve de una temporada a "
        "otra, lo más probable no es que sus equipos hayan cambiado de estilo a la "
        "vez, sino que cambió el criterio arbitral — el mismo patrón aparece en las "
        "faltas."
    )


def disciplina(df, season, seasons):
    d = df[df["temporada"] == season]
    prom = d.groupby("liga", observed=True)[COL_CRDY].mean().sort_values(ascending=False)
    mas, menos = prom.index[0], prom.index[-1]
    fija = (f"**{mas}** es la más tarjetera de {season} con "
            f"{_fmt(prom.iloc[0])} amarillas por 90', un "
            f"{_pct(prom.iloc[0], prom.iloc[-1]):.0f}% más que **{menos}** "
            f"({_fmt(prom.iloc[-1])}).")

    base = seasons[0]
    if season != base:
        antes = df[df["temporada"] == base].groupby("liga", observed=True)[COL_CRDY].mean()
        n_baja = int((prom < antes.reindex(prom.index)).sum())
        brecha_antes = _pct(antes.max(), antes.min())
        brecha_ahora = _pct(prom.iloc[0], prom.iloc[-1])
        v_media = _verbo(prom.mean(), antes.mean(), "bajó", "subió")
        v_brecha = _verbo(brecha_ahora, brecha_antes, "se achicó", "se ensanchó")
        cierre = ""
        if brecha_ahora < brecha_antes - 5:
            cierre = " — las 5 ligas se parecen cada vez más entre sí."
        elif brecha_ahora > brecha_antes + 5:
            cierre = " — las ligas se separaron, no al revés."
        salta = (f"Respecto de {base} la media de las 5 ligas {v_media} de "
                 f"{_fmt(antes.mean())} a {_fmt(prom.mean())} ({n_baja} de las 5 "
                 f"bajaron), y la distancia entre la más y la menos tarjetera "
                 f"{v_brecha} del {brecha_antes:.0f}% al {brecha_ahora:.0f}%{cierre}")
        if not cierre:
            salta += "."
    else:
        extremo = d.loc[d[COL_CRDY].idxmax()]
        salta = (f"El equipo más tarjetero de la temporada es **{extremo['Squad']}** "
                 f"({_fmt(extremo[COL_CRDY])} por 90'), muy por encima de la media "
                 f"de su liga ({_fmt(prom[extremo['liga']])}).")
    return fija, salta


# --------------------------------------------------------------------------
# Perfil de liga sobrepuesto — el mismo radar, mirando la separación
# --------------------------------------------------------------------------

def overlay_que_mirar():
    return ("Las 5 formas encimadas: donde los contornos se pisan, las ligas se "
            "parecen; donde uno se despega, ahí hay una diferencia real. Las barras "
            "de la derecha ponen número a eso, eje por eje.")


def overlay_por_que():
    return (
        "La barra es `1 − (mínimo ÷ máximo)` entre las 5 ligas: qué fracción del eje "
        "separa a la primera de la última. Se prefirió a la desviación estándar "
        "porque con 5 valores una desviación no significa gran cosa, y porque este "
        "número se lee directo — 30% quiere decir que la última liga se queda a un "
        "30% de la primera.\n\n"
        "El orden de las barras está fijado con el promedio de las 5 temporadas y no "
        "se reordena al cambiar de una a otra: si las filas saltaran de lugar en cada "
        "cambio no se podría ver qué eje sube y cuál baja, que es lo que interesa."
    )


def overlay(avg, labels, season, seasons):
    sub = avg.loc[season]
    sep = ((1 - sub.min() / sub.max()) * 100).sort_values(ascending=False)
    eje = sep.index[0]
    fija = (f"En {season} el eje que más separa a las ligas es **{labels[eje]}**: "
            f"la última se queda un {sep.iloc[0]:.0f}% por debajo de la primera. "
            f"En los otros siete la separación va del {sep.iloc[-1]:.0f}% al "
            f"{sep.iloc[1]:.0f}%.")

    # Cuánto se mueve la separación de ese eje entre temporadas: dice si la
    # diferencia es estructural o cosa de un año.
    serie = [((1 - avg.loc[s].min() / avg.loc[s].max()) * 100)[eje] for s in seasons]
    estable = max(serie) - min(serie) < 10
    salta = (f"En **{labels[eje]}** la separación va del {min(serie):.0f}% al "
             f"{max(serie):.0f}% según la temporada, así que es "
             f"{'una diferencia estable entre ligas' if estable else 'inestable: depende bastante del año'}.")
    return fija, salta


# --------------------------------------------------------------------------
# Evolución del estilo por liga (el control es la métrica, no la temporada)
# --------------------------------------------------------------------------

def evolucion_que_mirar():
    return ("Cada línea es una liga a lo largo de las 5 temporadas. Lo que importa "
            "es si las líneas **se mueven juntas** —eso apunta a un cambio de la "
            "competición o del arbitraje, no de los equipos— o si una se separa del "
            "resto por su cuenta.")


def evolucion_por_que():
    return (
        "Va en valor real y no escalado, al revés que el radar, porque acá la "
        "pregunta es de magnitud: cuántas faltas menos se pitan hoy que en 2021-22. "
        "Escalar lo escondería.\n\n"
        "El rango del eje Y se fija por métrica, con un poco de aire. Si se dejara "
        "automático, cada métrica se ajustaría a su propia escala y una caída de dos "
        "décimas se vería igual de dramática que una de dos unidades."
    )


def evolucion(avg_evol, labels, col, seasons):
    """`avg_evol` es el promedio por (temporada, liga) en formato largo."""
    piv = avg_evol.pivot(index="temporada", columns="liga", values=col)
    ini, fin = piv.loc[seasons[0]], piv.loc[seasons[-1]]
    v = _verbo(fin.mean(), ini.mean(), "bajó", "subió")
    n_baja = int((fin < ini).sum())
    fija = (f"En las 5 temporadas la media de **{labels[col]}** {v} de "
            f"{_fmt(ini.mean())} a {_fmt(fin.mean())} "
            f"({n_baja} de las 5 ligas a la baja).")

    if n_baja in (0, 5):
        salta = ("Se movieron **las 5 ligas en la misma dirección**, y eso es lo "
                 "interesante: que 96 equipos cambien a la vez apunta a la "
                 "competición o al criterio arbitral, no a una decisión táctica de "
                 "cada club.")
    else:
        cambio = (fin - ini).abs()
        liga = cambio.idxmax()
        v2 = _verbo(fin[liga], ini[liga], "bajó", "subió")
        salta = (f"La que más se movió es **{liga}**, que {v2} de "
                 f"{_fmt(ini[liga])} a {_fmt(fin[liga])} "
                 f"({_pct(fin[liga], ini[liga]):+.0f}%), mientras las otras cuatro se "
                 f"movieron menos.")
    return fija, salta


# --------------------------------------------------------------------------
# Portería vs. resultado — CS% vs. puntos por partido
# --------------------------------------------------------------------------

def porteria_que_mirar():
    return ("Cada punto es un equipo: a la derecha los que dejan más partidos con la "
            "portería a cero, arriba los que más puntos sacan. La nube sube en "
            "diagonal, y esa diagonal es justamente la advertencia del gráfico.")


def porteria_por_que(df):
    r = df["gk_Performance_CS%"].corr(df["pt_Team Success_PPM"])
    return (
        f"Estas dos variables correlacionan **{_fmt(r)}**, que es muchísimo. Por eso "
        f"el gráfico no se lee como \"tener buen portero da puntos\": las porterías a "
        f"cero son, en buena medida, **otra forma de medir lo bueno que es el "
        f"equipo**. Un equipo que domina concede poco, y conceder poco produce "
        f"porterías a cero.\n\n"
        f"Y no es un caso aislado: con datos públicos, casi cualquier métrica que "
        f"parezca de estilo termina midiendo nivel. Para juzgar al portero hay que "
        f"separar cuánto le disparan de cuánto ataja, que es lo que hace el gráfico "
        f"siguiente."
    )


def porteria(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    top = d.loc[d["gk_Performance_CS%"].idxmax()]
    fija = (f"En {ambito}, **{top['Squad']}** dejó la portería a cero en el "
            f"{_fmt(top['gk_Performance_CS%'], 1)}% de sus partidos, el máximo, con "
            f"{_fmt(top['gk_ppm'])} puntos por partido.")

    if len(d) < 4:
        return fija, None
    # Quién rompe la diagonal: muchos puntos con pocas porterías a cero.
    rx = d["gk_Performance_CS%"].rank(pct=True)
    ry = d["gk_ppm"].rank(pct=True)
    e = d.loc[(ry - rx).idxmax()]
    salta = (f"**{e['Squad']}** es el que más se sale de la diagonal: saca "
             f"{_fmt(e['gk_ppm'])} puntos por partido dejando la portería a cero solo "
             f"el {_fmt(e['gk_Performance_CS%'], 1)}% de las veces. Gana los partidos "
             f"por delante, no por detrás.")
    return fija, salta


# --------------------------------------------------------------------------
# Exigencia vs. rendimiento — SoTA vs. Save%
# --------------------------------------------------------------------------

def exigencia_que_mirar():
    return ("A la derecha, los porteros a los que más les disparan a puerta; arriba, "
            "los que mejor tasa de atajada tienen. Son dos preguntas distintas: "
            "**cuánto trabajo le cae** y **qué tan bien lo resuelve**.")


def exigencia_por_que(df):
    r_ind = df["gk_Performance_SoTA"].corr(df["gk_Performance_Save%"])
    r_conf = df["gk_Performance_SoTA"].corr(df["gk_Performance_GA90"])
    return (
        f"Este es el gráfico que arregla el problema del anterior. Los tiros a puerta "
        f"enfrentados (SoTA) correlacionan **{_fmt(r_conf)}** con los goles "
        f"recibidos: buena parte de lo que parece mérito o demérito del portero es en "
        f"realidad cuánto lo expone su defensa.\n\n"
        f"Al darle su propio eje, la tasa de atajadas queda libre de esa "
        f"contaminación: las dos correlacionan apenas **{_fmt(r_ind)}**, "
        f"prácticamente nada. Por eso van en ejes separados y no combinadas en un "
        f"índice — se comprobó que fueran independientes **antes** de dibujar el "
        f"gráfico, para no acabar graficando dos veces la misma señal.\n\n"
        f"Los penales quedan fuera a propósito: un equipo enfrenta entre 0 y 12 en "
        f"toda la temporada, y un porcentaje de atajada sobre esa base es ruido."
    )


def exigencia(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    mas = d.loc[d["gk_Performance_SoTA"].idxmax()]
    mejor = d.loc[d["gk_Performance_Save%"].idxmax()]
    fija = (f"En {ambito}, al portero de **{mas['Squad']}** es al que más le "
            f"dispararon a puerta ({int(mas['gk_Performance_SoTA'])} tiros) y el de "
            f"**{mejor['Squad']}** es el de mejor tasa de atajada "
            f"({_fmt(mejor['gk_Performance_Save%'], 1)}%).")

    if len(d) < 4:
        return fija, None
    # Lo valioso: mucha exigencia y aun así buena tasa.
    rx = d["gk_Performance_SoTA"].rank(pct=True)
    ry = d["gk_Performance_Save%"].rank(pct=True)
    e = d.loc[(rx + ry).idxmax()]
    salta = (f"El caso más meritorio es **{e['Squad']}**: recibió "
             f"{int(e['gk_Performance_SoTA'])} tiros a puerta —de los más castigados— "
             f"y aun así atajó el {_fmt(e['gk_Performance_Save%'], 1)}%. Mucho trabajo "
             f"y bien hecho, que es lo que el gráfico anterior no deja ver.")
    return fija, salta


# --------------------------------------------------------------------------
# Paridad competitiva — dispersión de puntos por partido
# --------------------------------------------------------------------------

COL_PPM = "pt_Team Success_PPM"


def paridad_que_mirar():
    return ("Acá no interesa dónde está la caja sino **qué tan alta es**: una caja "
            "corta es una liga pareja, donde casi todos suman parecido; una caja "
            "larga, una liga de dos velocidades. El porcentaje sobre cada una es el "
            "coeficiente de variación.")


def paridad_por_que():
    return (
        "La medida de dispersión es el **coeficiente de variación** (desviación "
        "estándar ÷ media, en %) y no el rango entre el primero y el último, porque "
        "el rango lo decide un solo equipo: un descendido histórico hunde el mínimo y "
        "hace parecer desigual a una liga que no lo es. El coeficiente usa a los 18 o "
        "20 equipos.\n\n"
        "Va sobre puntos **por partido** y no puntos totales porque la Bundesliga "
        "juega 34 jornadas y las otras cuatro 38: en total, sus equipos parecerían "
        "peores solo por jugar menos."
    )


def paridad(df, season, seasons):
    d = df[df["temporada"] == season]
    cv = (d.groupby("liga", observed=True)[COL_PPM]
          .agg(lambda s: s.std() / s.mean() * 100).sort_values(ascending=False))
    fija = (f"En {season} la liga más desigual es **{cv.index[0]}** "
            f"({cv.iloc[0]:.0f}% de variación) y la más pareja **{cv.index[-1]}** "
            f"({cv.iloc[-1]:.0f}%).")

    rango = cv.iloc[0] - cv.iloc[-1]
    todas = (df.groupby(["temporada", "liga"], observed=True)[COL_PPM]
             .agg(lambda s: s.std() / s.mean() * 100))
    if rango < 8:
        salta = (f"Aun así las 5 se parecen bastante: entre la más desigual y la más "
                 f"pareja hay {rango:.0f} puntos porcentuales. La idea de que una "
                 f"liga concreta es \"la de los dos equipos\" se sostiene menos de lo "
                 f"que suele decirse — en las {len(seasons)} temporadas el rango va "
                 f"del {todas.min():.0f}% al {todas.max():.0f}%.")
    else:
        salta = (f"La distancia entre la más desigual y la más pareja es de "
                 f"{rango:.0f} puntos porcentuales, bastante más de lo habitual: en "
                 f"las {len(seasons)} temporadas el coeficiente va del "
                 f"{todas.min():.0f}% al {todas.max():.0f}%.")
    return fija, salta


# --------------------------------------------------------------------------
# Edad de plantilla
# --------------------------------------------------------------------------

COL_EDAD = "ov_Age"


def edad_que_mirar():
    return ("La caja de cada liga muestra en qué franja de edad se mueven sus "
            "plantillas. Los puntos sueltos por abajo son proyectos jóvenes; por "
            "arriba, plantillas veteranas.")


def edad_por_que(df):
    r = df[COL_EDAD].corr(df[COL_PPM])
    return (
        f"Conviene decir lo que este gráfico **no** demuestra. La edad de plantilla "
        f"correlaciona **{_fmt(r)}** con los puntos por partido: prácticamente cero. "
        f"No hay una edad que gane partidos, ni los equipos jóvenes rinden peor ni "
        f"los veteranos mejor.\n\n"
        f"Sirve para otra cosa: leer la **estrategia de plantilla** de cada liga y de "
        f"cada club — quién apuesta por formar y vender y quién por fichar hecho. "
        f"Interpretarlo como una medida de calidad sería justo el error que el número "
        f"de arriba descarta."
    )


def edad(df, season, seasons):
    d = df[df["temporada"] == season]
    prom = d.groupby("liga", observed=True)[COL_EDAD].mean().sort_values()
    joven, veterana = d.loc[d[COL_EDAD].idxmin()], d.loc[d[COL_EDAD].idxmax()]
    fija = (f"En {season} la liga más joven es **{prom.index[0]}** "
            f"({_fmt(prom.iloc[0], 1)} años de media) y la más veterana "
            f"**{prom.index[-1]}** ({_fmt(prom.iloc[-1], 1)}).")
    salta = (f"Los extremos los ponen **{joven['Squad']}** "
             f"({_fmt(joven[COL_EDAD], 1)} años) y **{veterana['Squad']}** "
             f"({_fmt(veterana[COL_EDAD], 1)}): "
             f"{_fmt(veterana[COL_EDAD] - joven[COL_EDAD], 1)} años de diferencia "
             f"entre dos plantillas de la misma temporada.")
    return fija, salta


# ==========================================================================
# JUGADORES (Understat)
# ==========================================================================

# Tiene que coincidir con `MIN_MINUTES` de `web/charts/players.py`: allá filtra
# los datos y acá solo se nombra en los textos, así que si se separan la caja de
# lectura termina citando un umbral distinto del que se aplicó.
MIN_MINUTOS = 500


def _top_dif(d, real, esperado, n=1):
    """Quién más se pasa y quién más se queda corto respecto de lo esperado."""
    dif = d[real] - d[esperado]
    return d.loc[dif.idxmax()], d.loc[dif.idxmin()], dif


# --------------------------------------------------------------------------
# Goles vs. xG
# --------------------------------------------------------------------------

def goles_xg_que_mirar():
    return ("La diagonal marca \"marcó exactamente lo que se esperaba\". Por encima "
            "están los que metieron más de lo que decían sus ocasiones; por debajo, "
            "los que fallaron ocasiones claras. Cuanto más a la derecha, más "
            "ocasiones tuvo.")


def goles_xg_por_que(df):
    dif = (df["goals"] - df["xG"])
    return (
        f"El xG mide la **calidad de las ocasiones**, no el acierto: suma la "
        f"probabilidad de gol de cada remate según desde dónde y cómo se hizo. "
        f"Restarlo de los goles deja lo que el jugador puso de más (o de menos).\n\n"
        f"Dos advertencias que valen más que el gráfico. Primera: **la distancia a la "
        f"diagonal es casi toda azar**. En el análisis de definición de la sección de "
        f"Machine Learning se midió sobre 221.922 tiros que la habilidad de definir "
        f"existe pero explica solo el 14% de la variación, y que de una temporada a "
        f"la siguiente se repite con r = 0.09 — o sea que quien está muy arriba este "
        f"año probablemente no lo esté el próximo.\n\n"
        f"Segunda: el xG que se usa acá es el de Understat, y en ese mismo análisis "
        f"se comprobó que **sobreestima** (predice un 17% más goles de los que "
        f"entran). Eso empuja a toda la nube por debajo de la diagonal: el jugador "
        f"promedio queda {_fmt(dif.mean())} goles por debajo de su xG. La línea es "
        f"una referencia, no un cero calibrado.\n\n"
        f"El filtro de {MIN_MINUTOS} minutos existe por lo mismo: sin él, cualquiera "
        f"con 200 minutos y dos goles de rebote encabezaría el ranking."
    )


def goles_xg(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    top = d.loc[d["goals"].idxmax()]
    fija = (f"En {ambito}, el máximo goleador es **{top['player']}** "
            f"({top['team']}) con {int(top['goals'])} goles sobre "
            f"{_fmt(top['xG'], 1)} de xG.")

    if len(d) < 5:
        return fija, None
    arriba, abajo, dif = _top_dif(d, "goals", "xG")
    salta = (f"El que más superó su xG es **{arriba['player']}** "
             f"(+{_fmt(dif.max(), 1)} goles) y el que más se quedó corto, "
             f"**{abajo['player']}** ({_fmt(dif.min(), 1)}). Antes de sacar "
             f"conclusiones: una diferencia así se repite poco de una temporada a la "
             f"siguiente.")
    return fija, salta


# --------------------------------------------------------------------------
# Asistencias vs. xA
# --------------------------------------------------------------------------

def asist_xa_que_mirar():
    return ("Mismo esquema que el de goles pero para crear: la diagonal es \"asistió "
            "lo que sus pases merecían\". Por encima, jugadores cuyos compañeros "
            "definieron bien lo que les pusieron.")


def asist_xa_por_que(df):
    r = df["xA"].corr(df["a"])
    return (
        f"El xA mide la calidad de los pases de gol que dio un jugador: **cuánta "
        f"probabilidad de gol generó el remate que habilitó**. Correlaciona "
        f"{_fmt(r)} con las asistencias reales.\n\n"
        f"La diferencia clave con el gráfico de goles: acá el que está por encima de "
        f"la diagonal **no hizo nada distinto**. Una asistencia depende de que otro "
        f"la meta, así que estar arriba dice sobre todo que quien remató estuvo "
        f"acertado. Es todavía menos atribuible al jugador que la diferencia entre "
        f"goles y xG, y por eso conviene leerlo como una medida de creación de "
        f"ocasiones (el eje horizontal) más que de rendimiento sobre lo esperado."
    )


def asist_xa(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    top = d.loc[d["a"].idxmax()]
    creador = d.loc[d["xA"].idxmax()]
    fija = (f"En {ambito} el que más asistió es **{top['player']}** ({top['team']}) "
            f"con {int(top['a'])}, y el que más ocasiones generó es "
            f"**{creador['player']}** ({_fmt(creador['xA'], 1)} de xA).")

    if len(d) < 5:
        return fija, None
    arriba, _, dif = _top_dif(d, "a", "xA")
    salta = (f"**{arriba['player']}** es el que más se pasa de su xA "
             f"(+{_fmt(dif.max(), 1)} asistencias), pero eso habla tanto de él como "
             f"de los que remataron sus pases.")
    return fija, salta


# --------------------------------------------------------------------------
# Perfil ofensivo — xG90 vs. xA90
# --------------------------------------------------------------------------

def perfil_que_mirar():
    return ("Las líneas punteadas son el promedio de cada eje. Abajo a la derecha, "
            "rematadores puros; arriba a la izquierda, creadores puros; arriba a la "
            "derecha, los que hacen las dos cosas — que son pocos y suelen ser los "
            "nombres que uno espera.\n\n"
            "Ojo con leer la nube entera de un saque: **buena parte de la distancia "
            "entre dos puntos es el puesto en el que juegan**, no lo bueno que es cada "
            "uno. Un central y un extremo caen lejísimos sin que eso diga nada de "
            "ninguno de los dos. El filtro de posición de la barra lateral deja la "
            "comparación entre iguales, que es donde un xG90 alto empieza a significar "
            "algo.")


def perfil_por_que(df):
    r = df["xG90"].corr(df["xA90"])
    return (
        f"Va en tasas por 90 minutos y no en totales para que un suplente que rinde "
        f"mucho en poco tiempo no quede sepultado por un titular indiscutido. El "
        f"filtro de {MIN_MINUTOS} minutos compensa el efecto contrario: sin él, unos "
        f"pocos minutos con una ocasión clara dan una tasa altísima que es puro "
        f"ruido.\n\n"
        f"Se usa **xG90 y xA90 en vez de goles y asistencias** porque a este nivel de "
        f"detalle la muestra por jugador es chica y los goles son un evento raro: lo "
        f"esperado es una medida mucho más estable de lo que un jugador genera que lo "
        f"que efectivamente entró.\n\n"
        f"Los dos ejes correlacionan {_fmt(r)}: comparten algo (los buenos atacantes "
        f"tienden a participar en todo) pero dejan sitio de sobra para perfiles "
        f"distintos, que es lo que hace que valga la pena cruzarlos."
    )


def perfil(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    rematador = d.loc[d["xG90"].idxmax()]
    creador = d.loc[d["xA90"].idxmax()]
    fija = (f"En {ambito}, el perfil más rematador es **{rematador['player']}** "
            f"({_fmt(rematador['xG90'])} xG90) y el más creador "
            f"**{creador['player']}** ({_fmt(creador['xA90'])} xA90).")

    if len(d) < 5:
        return fija, None
    # Todocampo: el mejor en la suma de ambos percentiles, estando arriba en los dos.
    rx, ry = d["xG90"].rank(pct=True), d["xA90"].rank(pct=True)
    completo = d.loc[(rx + ry).idxmax()]
    n_ambos = int(((d["xG90"] > d["xG90"].mean()) & (d["xA90"] > d["xA90"].mean())).sum())
    salta = (f"El perfil más completo es **{completo['player']}** "
             f"({_fmt(completo['xG90'])} xG90 y {_fmt(completo['xA90'])} xA90). Solo "
             f"{n_ambos} de {len(d)} jugadores superan el promedio en los dos ejes a "
             f"la vez: hacer las dos cosas es raro.")
    return fija, salta


# --------------------------------------------------------------------------
# Nivel goleador / de creación por liga (boxplots)
# --------------------------------------------------------------------------

def nivel_que_mirar(que):
    return (f"Cada punto es un jugador y la caja marca dónde cae la mitad central de "
            f"cada liga. Interesa comparar **la altura de las cajas** (si una liga "
            f"genera más {que} que otra) y **los puntos sueltos de arriba**, que son "
            f"los jugadores que se escapan de su propia liga.")


def nivel_por_que(col):
    es_gol = col == "xG90"
    cual = "xG por 90'" if es_gol else "xA por 90'"
    if es_gol:
        esperado = (
            f"Y va sobre lo **esperado** y no sobre goles reales porque a nivel de "
            f"jugador la muestra es chica: un delantero remata unas cien veces en una "
            f"temporada, y sobre esa base los goles oscilan mucho por azar. El xG "
            f"acumula la probabilidad de cada remate, así que da una lectura mucho "
            f"más estable del nivel goleador de la liga."
        )
        filtro = ("un jugador con 150 minutos y una ocasión clara aparecería como el "
                  "más peligroso de su liga.")
    else:
        esperado = (
            f"Y va sobre lo **esperado** y no sobre asistencias reales porque una "
            f"asistencia solo existe si otro la mete: mide al que remató tanto como "
            f"al que dio el pase. El xA le pone a cada pase la probabilidad de gol "
            f"del remate que habilitó, haya entrado o no, así que se queda con la "
            f"parte que sí hizo el creador y da una lectura mucho más estable del "
            f"nivel de creación de la liga."
        )
        filtro = ("un jugador con 150 minutos y un pase que dejó a un compañero solo "
                  "aparecería como el más creador de su liga.")
    return (
        f"Se grafica {cual} y no el total de la temporada porque el total mezcla dos "
        f"cosas: lo bueno que es un jugador y cuánto jugó. La tasa aísla la primera.\n\n"
        f"{esperado}\n\n"
        f"El filtro de {MIN_MINUTOS} minutos deja fuera a quien jugó poco: sin él, "
        f"{filtro}"
    )


def nivel(df, col, season):
    d = df[df["temporada"] == season]
    med = d.groupby("liga", observed=True)[col].median().sort_values(ascending=False)
    top = d.loc[d[col].idxmax()]
    fija = (f"En {season} la liga con el nivel mediano más alto es **{med.index[0]}** "
            f"({_fmt(med.iloc[0])}) y la más baja **{med.index[-1]}** "
            f"({_fmt(med.iloc[-1])}).")
    salta = (f"La diferencia entre ligas es chica comparada con la que hay **dentro** "
             f"de cada una: el máximo de la temporada lo tiene **{top['player']}** "
             f"({top['team']}) con {_fmt(top[col])}, unas "
             f"{top[col] / med.iloc[0]:.0f} veces la mediana de su propia liga.")
    return fija, salta


# --------------------------------------------------------------------------
# Mapa de calor de los tiros
# --------------------------------------------------------------------------
#
# Los tres textos trabajan sobre el DataFrame que arma `shot_map.py`: un tiro
# por fila, ya recortado a la región del mapa, con las columnas derivadas que
# ahí se calculan (`dist`, `gol`, `en_area`, `en_area_chica`, `izquierda`).
# La geometría vive allá y no acá a propósito — el mapa y el texto tienen que
# estar de acuerdo en qué es "dentro del área", y la única forma de garantizarlo
# es que haya una sola definición.

# Umbrales de lo que cuenta como notable para elegir el dato que salta. Están
# en las unidades de cada cosa (puntos porcentuales, metros) y se usan para
# ponerlas en la misma escala: el candidato con el cociente más alto gana, y si
# ninguno llega a 1 es que la selección no se separa del tiro medio en nada.
NOTABLE_LADO, NOTABLE_DIST, NOTABLE_CONV, NOTABLE_CHICA = 1.5, 3.0, 1.5, 6.0


def miles(n):
    return f"{int(n):,}".replace(",", ".")


def tiros_que_mirar():
    return ("El mapa mira **hacia la portería**: la línea de fondo es el borde de "
            "arriba, los dos rectángulos son el área grande y el área chica, y la "
            "izquierda del mapa es la izquierda del ataque.\n\n"
            "Cada celda es un cuadrado de 2×2 m, y el color **no cuenta tiros**: "
            "reparte entre las celdas el 100% de los tiros que estás viendo. Una "
            "celda oscura dice \"de aquí salió una parte grande de estos tiros\", "
            "no \"de aquí salieron muchos tiros\". El reparto se rehace cada vez "
            "que cambias un filtro, y por eso la forma de un tipo de tiro se puede "
            "comparar con la de otro aunque haya veinte veces más de uno que de "
            "otro.\n\n"
            "Pasa el mouse por una celda para ver los números crudos: cuántos "
            "tiros salieron de ahí y cuántos acabaron en gol.")


def tiros_por_que(n_mapa, n_penales, n_fuera):
    return (
        f"**Los penaltis quedan fuera** ({miles(n_penales)} en las 5 temporadas). "
        f"Understat los registra a todos en exactamente el mismo punto, así que en "
        f"un mapa de 2×2 m caen en una sola celda y la convierten en la más caliente "
        f"de todas — sin decir nada sobre desde dónde remata un equipo, que es la "
        f"pregunta del gráfico.\n\n"
        f"**El mapa llega hasta 36 m de la línea de fondo** y ahí se corta. Los "
        f"{miles(n_fuera)} tiros de más lejos son el "
        f"{100 * n_fuera / (n_mapa + n_fuera):.1f}% del total y están tan repartidos "
        f"que solo agregarían cancha vacía.\n\n"
        f"**Las opciones del filtro se cruzan entre sí.** Los cuatro tipos de jugada "
        f"sí son excluyentes, pero \"cabezazo\" los atraviesa a todos: un cabezazo "
        f"puede venir de un córner igual que de jugada abierta. Por eso cada mapa se "
        f"calcula sobre el total de **su propia** selección y no sobre los "
        f"{miles(n_mapa)} tiros del conjunto: si se calculara sobre el conjunto, el "
        f"mapa de cabezazo se vería casi vacío al lado del de jugada abierta y no "
        f"habría forma de compararlos."
    )


def tiros(sub, base, frase, ambito):
    """(fija, salta) del mapa de calor para una combinación temporada × tipo.

    `sub` son los tiros de la combinación elegida y `base` los de esa misma
    temporada sin filtro de tipo: la referencia contra la que se mide si el tipo
    elegido se remata desde más cerca, más lejos, más de un lado o con más
    puntería. `frase` es cómo se nombra el tipo dentro de la oración ("de
    córner", "con el pie izquierdo", "" para todos)."""
    if sub.empty:
        return "No hay tiros de este tipo en la temporada elegida.", None

    n = len(sub)
    area, dist = 100 * sub["en_area"].mean(), sub["dist"].mean()
    conv = 100 * sub["gol"].mean()
    # Una sola cifra de zona y no dos ("y el X% desde el área chica"): con el
    # tiro libre directo, que por definición no puede salir de dentro del área,
    # la segunda mitad quedaba en "el 0% y el 0%". El área chica se cuenta en el
    # dato que salta, donde solo aparece cuando dice algo.
    fija = (f"De los {miles(n)} tiros {frase}de {ambito}, el **{area:.0f}%** salió "
            f"desde dentro del área. La distancia media a la portería fue de "
            f"{_fmt(dist, 1)} m y acabó en gol el {_fmt(conv, 1)}%.")

    # El dato que salta: de qué se separa esta selección respecto del tiro medio
    # de la misma temporada. Los candidatos se normalizan por su umbral de
    # notabilidad para poder compararlos entre sí (ver arriba).
    izq, izq_base = 100 * sub["izquierda"].mean(), 100 * base["izquierda"].mean()
    chica, chica_base = (100 * sub["en_area_chica"].mean(),
                         100 * base["en_area_chica"].mean())
    dist_base, conv_base = base["dist"].mean(), 100 * base["gol"].mean()
    peso, cual = max([
        (abs(izq - 50) / NOTABLE_LADO, "lado"),
        (abs(dist - dist_base) / NOTABLE_DIST, "dist"),
        (abs(conv - conv_base) / NOTABLE_CONV, "conv"),
        (abs(chica - chica_base) / NOTABLE_CHICA, "chica"),
    ])

    if peso < 1:
        # Ninguna selección se separa del promedio: entonces lo que vale la pena
        # contar es la propia estructura del mapa, que siempre está ahí.
        dentro, fuera = sub[sub["en_area"]], sub[~sub["en_area"]]
        salta = (f"El {100 - area:.0f}% se remató desde fuera del área, y de esos "
                 f"entró solo el {_fmt(100 * fuera['gol'].mean(), 1)}% contra el "
                 f"{_fmt(100 * dentro['gol'].mean(), 1)}% de los de dentro.")
    elif cual == "lado":
        salta = (f"El **{izq:.0f}%** salió desde la mitad izquierda del ataque y el "
                 f"{100 - izq:.0f}% desde la derecha, contra un reparto de "
                 f"{izq_base:.0f}/{100 - izq_base:.0f} en el tiro medio de "
                 f"{ambito}.")
    elif cual == "dist":
        salta = (f"Se remata desde mucho más **{_verbo(dist, dist_base, 'cerca', 'lejos')}** "
                 f"que el tiro medio de {ambito}: {_fmt(dist, 1)} m contra "
                 f"{_fmt(dist_base, 1)} m.")
    elif cual == "chica":
        salta = (f"El **{chica:.0f}%** salió desde el área chica, contra el "
                 f"{chica_base:.0f}% del tiro medio de {ambito}.")
    else:
        salta = (f"Entra el **{_fmt(conv, 1)}%** contra el {_fmt(conv_base, 1)}% del "
                 f"tiro medio de {ambito}, aun rematando desde "
                 f"{_verbo(dist, dist_base, 'más cerca', 'más lejos', igual='la misma distancia')}.")
    return fija, salta
