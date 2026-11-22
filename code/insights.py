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
# Eficiencia de definición con proxies de FBref (SoT% vs. G/SoT). Ya no está en el sitio: lo usa
# el notebook `eda_teams.ipynb`. La vista del sitio con este nombre es `definicion`, con xG.
# --------------------------------------------------------------------------

X_DEF, Y_DEF = "sh_Standard_SoT%", "sh_Standard_G/SoT"


def definicion_sot_que_mirar():
    return ("Arriba a la derecha están los que hacen bien las dos cosas; abajo a la "
            "derecha, los que llevan a puerta buena parte de sus tiros y marcan poco de "
            "ellos.")


def definicion_sot_por_que(df):
    r = df[X_DEF].corr(df[Y_DEF])
    return (
        f"Las dos van en ejes separados porque **no son la misma habilidad**: "
        f"correlacionan {_fmt(r)} sobre las {miles(len(df))} observaciones, o sea que "
        f"comparten apenas un {r ** 2 * 100:.0f}% de su variación. Un equipo puede "
        f"ser muy bueno generando remates claros y flojo rematándolos, y al revés. "
        f"Si se mezclaran en un solo indicador de \"eficiencia\" esa distinción se "
        f"perdería, que es justo lo que el gráfico quiere mostrar."
    )


def definicion_sot(df, season, liga=None):
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
        "Van **por 90 minutos** y no en total porque no todas las ligas juegan las mismas "
        "jornadas (la Bundesliga siempre 34, la Ligue 1 desde 2023-24, las otras tres 38): en "
        "bruto, las ligas con menos partidos parecerían más disciplinadas solo por jugar menos.\n\n"
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
        "Va en valor real y no escalado, al revés que el radar, porque aquí la "
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
        "Va sobre puntos **por partido** y no puntos totales porque no todas las ligas "
        "juegan las mismas jornadas (la Bundesliga siempre 34, la Ligue 1 desde 2023-24, las "
        "otras tres 38): en total, las que juegan menos parecerían peores solo por jugar menos."
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


def _corte():
    """El corte de minutos tal como se aplica (`players.MIN_MINUTES_POR_TEMPORADA`): el número fijo vale
    para las temporadas cerradas, y el subtítulo de la gráfica dice el de la que se ve."""
    return f"el corte de minutos ({MIN_MINUTOS} en una temporada cerrada; menos en la que va en curso)"


def _frase_ambos(x, y):
    """Cuántos superan el promedio en los dos ejes, contra los que saldrían si un eje no tuviera que ver con
    el otro. Con distribuciones sesgadas menos de la mitad supera el promedio de cada eje, así que "pocos"
    se mide contra eso. Mismo texto que `frasesAmbos` de `web/react/src/insights.js`."""
    n = len(x)
    ax, ay = x > x.mean(), y > y.mean()
    n_ambos = int((ax & ay).sum())
    esperado = int(ax.sum() * ay.sum() / n + 0.5)
    base = f"{miles(n_ambos)} de {miles(n)} jugadores superan el promedio en los dos ejes a la vez"
    if n_ambos > esperado * 1.15:
        return (f"{base}, más de los {miles(esperado)} que saldrían si un eje no tuviera que ver con el otro: "
                f"hacer una cosa suele ir con la otra.")
    if n_ambos < esperado * 0.85:
        return (f"Solo {base}, menos de los {miles(esperado)} que saldrían si un eje no tuviera que ver con el "
                f"otro: hacer las dos cosas es raro.")
    return f"{base}, más o menos los {miles(esperado)} que saldrían si un eje no tuviera que ver con el otro."


def _cuanto(r):
    """Qué tanto se pisan dos ejes, con las bandas de "Crea tu gráfico" (`banda` en insights.js)."""
    a = abs(r)
    if a < 0.3:
        return "casi no van de la mano"
    if a < 0.6:
        return "van de la mano solo en parte"
    if a < 0.85:
        return "van bastante de la mano"
    return "son casi la misma información"


def _persistencia(df, real, esperado, minimo=900):
    """Cuánto se repite (real − esperado) por 90' de una temporada a la siguiente: la correlación entre
    temporadas cerradas seguidas, con los jugadores que pasan de `minimo` minutos en las dos. Un nombre
    repetido en una temporada (dos jugadores que se llaman igual) queda fuera. Devuelve `(lo, hi)` o None.
    Cerrada = alguien pasó de 2,500 minutos (la que va en curso no llega)."""
    cerradas = [t for t, m in df.groupby("temporada")["min"].max().items() if m >= 2500]
    rs = []
    for a, b in zip(cerradas, cerradas[1:]):
        d = []
        for t in (a, b):
            x = df[(df["temporada"] == t) & (df["min"] >= minimo)].drop_duplicates("player", keep=False)
            d.append(((x[real] - x[esperado]) / x["min"] * 90).set_axis(x["player"]))
        comun = d[0].index.intersection(d[1].index)
        if len(comun) >= 100:
            rs.append(d[0][comun].corr(d[1][comun]))
    return (min(rs), max(rs)) if rs else None


def _top_dif(d, real, esperado, n=1):
    """Quién más se pasa y quién más se queda corto respecto de lo esperado."""
    dif = d[real] - d[esperado]
    return d.loc[dif.idxmax()], d.loc[dif.idxmin()], dif


# --------------------------------------------------------------------------
# Goles vs. xG
# --------------------------------------------------------------------------

def goles_xg_que_mirar():
    return ("Cuanto más a la derecha, más ocasiones tuvo. La diagonal marca \"marcó exactamente lo que se "
            "esperaba\" y la franja gris, hasta dónde llega el azar: dentro de ella, la diferencia con el xG es lo "
            "que se esperaría solo por suerte.")


def _frase_persistencia(df, real, esperado, que):
    p = _persistencia(df, real, esperado)
    if not p:
        return ""
    lo, hi = p
    return (f" De una temporada cerrada a la siguiente, esa diferencia correlaciona entre {_fmt(lo)} y {_fmt(hi)} "
            f"(jugadores con más de 900 minutos en las dos): casi nada se repite.")


def goles_xg_por_que(df):
    dif = (df["np_goals"] - df["np_xg"])
    tira = df[df["goals"] != df["np_goals"]]            # jugador-temporadas con algún penal anotado
    cambia = int((((tira["goals"] - tira["xG"]) > 0) != ((tira["np_goals"] - tira["np_xg"]) > 0)).sum())
    return (
        f"El xG mide la **calidad de las ocasiones**, no el acierto: suma la "
        f"probabilidad de gol de cada remate según desde dónde y cómo se hizo. "
        f"Restarlo de los goles deja la definición más la suerte, y en una temporada "
        f"no hay forma de separarlas.\n\n"
        f"La gráfica va **sin penales**, en los goles y en el xG. Un penal vale cerca de 0.76 de xG y casi siempre "
        f"entra, así que quien los tira en su equipo aparece \"de más\" sin haber definido mejor. En estos datos, a "
        f"{miles(cambia)} de los {miles(len(tira))} jugador-temporadas con algún penal anotado el signo de "
        f"\"goles menos xG\" se invierte al quitarlos.\n\n"
        f"La **franja gris** es el azar: si un jugador definiera exactamente como se espera, sus goles caerían ahí "
        f"el 90% de las veces (la franja crece con la raíz del xG, porque con pocas ocasiones un gol más o menos "
        f"mueve mucho). Quien queda fuera de la franja se alejó de lo esperado más de lo que explica la suerte; "
        f"quien queda dentro, no se distingue de ella.\n\n"
        f"Primera advertencia: **una temporada es poca muestra para separar talento de "
        f"suerte**. Con unas decenas de remates, un par de goles de más o de menos "
        f"mueve mucho a un jugador respecto de la diagonal, así que quien está muy "
        f"arriba este año no necesariamente lo estará el próximo."
        + _frase_persistencia(df, "np_goals", "np_xg", "goles y xG sin penales") + "\n\n"
        f"Segunda: el xG que se usa aquí es el de Understat, y en estos datos suma "
        f"{'más' if dif.mean() < 0 else 'menos'} de lo que entra: el jugador promedio mete {_fmt(abs(dif.mean()))} goles "
        f"{'menos' if dif.mean() < 0 else 'más'} que su xG. Eso empuja a toda la nube "
        f"{'por debajo' if dif.mean() < 0 else 'por encima'} de la diagonal. La línea "
        f"es una guía, no un cero exacto.\n\n"
        f"{_corte().capitalize()} existe por lo mismo: sin él, cualquiera con 200 "
        f"minutos y dos goles de rebote encabezaría el ranking."
    )


def goles_xg(df, season, liga=None):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga

    top = d.loc[d["np_goals"].idxmax()]
    fija = (f"En {ambito}, el máximo goleador sin penales es **{top['player']}** "
            f"({top['team']}) con {int(top['np_goals'])} goles sobre "
            f"{_fmt(top['np_xg'], 1)} de xG.")

    if len(d) < 5:
        return fija, None
    arriba, abajo, dif = _top_dif(d, "np_goals", "np_xg")
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
    return ("Cuanto más a la derecha, más pases de peligro dio. Por encima de la diagonal "
            "están los jugadores cuyos compañeros definieron bien lo que les pusieron: "
            "parte del mérito es de quien remata.")


def asist_xa_por_que(df):
    r = df["xA"].corr(df["a"])
    return (
        f"El xA mide la calidad de los pases de gol que dio un jugador: **cuánta "
        f"probabilidad de gol generó el remate que habilitó**. Correlaciona "
        f"{_fmt(r)} con las asistencias reales.\n\n"
        f"La diferencia clave con el gráfico de goles: aquí el que está por encima de "
        f"la diagonal **no hizo nada distinto**. Una asistencia depende de que otro "
        f"la meta, así que estar arriba dice sobre todo que quien remató estuvo "
        f"acertado. Es todavía menos atribuible al jugador que la diferencia entre "
        f"goles y xG, y por eso conviene leerlo como una medida de creación de "
        f"ocasiones (el eje horizontal) más que de rendimiento sobre lo esperado."
        + _frase_persistencia(df, "a", "xA", "asistencias y xA")
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
    return (
        "Ubica a cada jugador según lo que genera con sus tiros y con sus pases, por 90 minutos. El eje horizontal es "
        "el xG, el peligro de sus remates, y el vertical es el xA, el peligro de los pases con los que habilita a "
        "otros.\n"
        "Las líneas marcan el 20% más alto de cada eje, así que pasar una de ellas indica que el jugador destaca en "
        "esa faceta, y arriba a la derecha están los que destacan en las dos.")


def perfil_por_que(df):
    r = df["xG90"].corr(df["xA90"])
    return (
        f"Va en tasas por 90 minutos para que un suplente que rinde mucho en poco tiempo no quede sepultado. "
        f"{_corte().capitalize()} evita lo contrario: unos pocos minutos con una ocasión clara dan una tasa que es puro "
        f"ruido.\n\n"
        f"Se usa **xG90 y xA90 en vez de goles y asistencias** porque los goles son un evento raro: lo esperado es una "
        f"medida más estable de lo que un jugador genera. Los dos ejes correlacionan {_fmt(r)}: {_cuanto(r)}. Dentro de "
        f"una posición, y sobre todo entre delanteros, rematar y crear van poco de la mano: son perfiles distintos."
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
    salta = (f"El perfil más completo es **{completo['player']}** "
             f"({_fmt(completo['xG90'])} xG90 y {_fmt(completo['xA90'])} xA90). "
             + _frase_ambos(d["xG90"], d["xA90"]))
    entre_ligas = _perfil_entre_ligas(d) if liga in (None, LIGA_TODAS) else ""
    if entre_ligas:
        salta += " " + entre_ligas
    return fija, salta


def _perfil_entre_ligas(d):
    """Qué tan distintas son las cinco ligas entre sí, comparado con lo que se
    estiran por dentro.

    Es lo que decían los dos boxplots por liga que hasta el 2026-09-01 fueron
    página aparte ("Nivel goleador / de creación esperado por liga") y hasta el
    2026-09-08, las cajas de los márgenes. Sin ellas la conclusión sigue en pie
    —se ve en cómo se mezclan los cinco colores de la nube—, así que se dice acá
    con números. Solo tiene sentido con más de una liga a la vista, así que
    quien llama la saltea cuando hay una sola elegida."""
    frases = []
    for col, nombre in (("xG90", "xG90"), ("xA90", "xA90")):
        med = d.groupby("liga", observed=True)[col].median().dropna()
        if len(med) < 2:
            continue
        lo, hi = _fmt(med.min()), _fmt(med.max())
        # Con un subconjunto chico (o de porteros, donde las cinco medianas son
        # 0.00) un "van de 0.00 a 0.00" se lee como un error; ahí lo que hay que
        # decir es que son la misma.
        frases.append(f"las de {nombre} son las cinco {lo}" if lo == hi
                       else f"las de {nombre} van de {lo} a {hi}")
    if not frases:
        return ""
    return (f"Y los cinco colores se mezclan más de lo que parece — las medianas "
            f"por liga: {' y '.join(frases)}. La diferencia **entre** ligas es mucho "
            f"más chica que la que hay **dentro** de cada una.")


# --------------------------------------------------------------------------
# Las dos gráficas defensivas (fbref)
# --------------------------------------------------------------------------
#
# Son las únicas de la sección que no salen de Understat: cada número es una
# cuenta de fbref dividida por minutos de fbref. Y son las únicas defensivas
# que se pueden hacer — de la página de acciones defensivas de fbref solo
# sobreviven entradas ganadas e intercepciones (el resto llega con las celdas
# vacías, verificado el 2026-09-01; está documentado en
# `fetch_fbref_players.EXTRA_TABLAS`), y Understat no publica ninguna.
#
# El aviso que las dos tienen que dar, y que no es un detalle: **el volumen
# defensivo lo manda el equipo**. Quien juega en un club que no tiene la pelota
# defiende más, y las tasas por 90' no lo arreglan. Por eso los dos textos
# mandan a los filtros de posición y de nivel de club, que es lo único que
# convierte la comparación en una comparación entre iguales.

def _parrafo(texto):
    """Un párrafo más, o nada. Sirve para enganchar avisos que solo aparecen
    cuando los datos los justifican, sin dejar el salto de línea colgando."""
    return f"\n\n{texto}" if texto else ""


def _quiebre_intercepciones(df, corto=False):
    """El aviso de que las intercepciones NO son comparables entre temporadas.

    Al bajar los datos (2026-09-01) apareció esto: la media de intercepciones
    por 90' cae ~19% entre la primera temporada y las últimas, **en las cinco
    ligas a la vez**, mientras las entradas ganadas se quedan planas. Cinco
    competiciones independientes no cambian igual el mismo año por razones de
    fútbol, y un cambio real de estilo no dejaría intacta la otra mitad de la
    acción defensiva: es un cambio de criterio de quien cuenta.

    Importa decirlo porque el eje va fijado sobre las 5 temporadas —para que
    cambiar de temporada sea una comparación honesta— y en esta columna esa
    promesa no se cumple. Se calcula en vez de escribirse a mano para que el
    día que se rebajen los datos la frase siga diciendo la verdad, o desaparezca
    si el quiebre desaparece."""
    por_temp = df.groupby("temporada")[["interceptions90", "tkl_w90"]].mean()
    if len(por_temp) < 3:
        return ""
    inter, tkl = por_temp["interceptions90"], por_temp["tkl_w90"]
    caida = (1 - inter.min() / inter.max()) * 100
    tkl_var = abs(1 - tkl.min() / tkl.max()) * 100
    if caida < 10 or caida < tkl_var * 2:
        return ""
    # El texto completo va una sola vez, en "Perfil defensivo" (donde las intercepciones son un eje);
    # las otras dos defensivas mandan ahí.
    if corto:
        return (f"**Las intercepciones no se comparan bien entre temporadas**: su media cae un "
                f"{caida:.0f}% entre {inter.idxmax()} y {inter.idxmin()} en las cinco ligas a la "
                f"vez. El detalle está en \"Perfil defensivo\".")
    return (
        f"**Las intercepciones no son comparables entre temporadas.** Su media por 90' cae un {caida:.0f}% entre "
        f"{inter.idxmax()} y {inter.idxmin()} (de {_fmt(inter.max())} a {_fmt(inter.min())}) en **las cinco ligas a la "
        f"vez**, mientras las entradas ganadas se mueven un {tkl_var:.0f}%: lo más probable es que haya cambiado el "
        f"criterio de quien cuenta el dato. Dentro de una temporada la comparación se sostiene; entre temporadas, no."
    )


def _defensa_ambito(df, season, liga):
    d = df[df["temporada"] == season]
    ambito = "las 5 ligas"
    if liga and liga != LIGA_TODAS:
        d = d[d["liga"] == liga]
        ambito = liga
    return d[d["recoveries90"].notna()], ambito


def recuperar_que_mirar():
    return ("Abajo a la derecha están los que roban mucho y limpio, que es el mejor sitio "
            "del gráfico; arriba a la izquierda, los que hacen faltas sin recuperar a "
            "cambio. Dos jugadores con el mismo volumen de recuperación pueden quedar muy "
            "separados en el eje vertical.\n\n"
            "Dos avisos antes de sacar conclusiones. **La posición manda**: un central y "
            "un extremo no compiten por lo mismo. Y **el equipo también**: quien juega en "
            "un club que no tiene la pelota defiende más, sin que eso diga nada de él. "
            "Los filtros de posición y de nivel del club son los que dejan la comparación "
            "entre iguales.")


def recuperar_por_que(df):
    d = df[df["recoveries90"].notna()]
    r = d["recoveries90"].corr(d["fouls90"])
    por_falta = d["recoveries"].sum() / d["fouls"].sum()
    return (
        f"Las dos maneras de quitar la pelota van **sumadas** en el eje X porque "
        f"aquí la pregunta no es cómo la recupera sino cuánta: entrar a disputar y "
        f"leer el pase terminan en lo mismo, la posesión cambia de dueño. Separarlas "
        f"es la otra gráfica.\n\n"
        f"La falta entra como el **precio** de recuperar. Cortar una "
        f"jugada con falta es una decisión defensiva legítima —a veces la correcta— "
        f"pero cuesta un balón parado en contra y acerca la tarjeta. En estos datos "
        f"se cometen {_fmt(1 / por_falta)} faltas por cada recuperación, y los dos "
        f"ejes correlacionan {_fmt(r)}: quien más defiende más falta, así que lo que "
        f"distingue a un jugador no es su altura en el gráfico sino cuánto se aparta "
        f"de esa tendencia.\n\n"
        f"Las tres columnas son de **FBref y no de Understat**, que solo registra "
        f"lo que pasa alrededor de los tiros y no publica ninguna acción defensiva. "
        f"Van divididas por los minutos de FBref y no por los de Understat: son "
        f"cuentas de una fuente, y su divisor tiene que ser de la misma. "
        f"{_corte().capitalize()} sí usa los minutos de Understat, como en el resto "
        f"de la sección."
        + _parrafo(_quiebre_intercepciones(d, corto=True))
    )


def recuperar(df, season, liga=None):
    d, ambito = _defensa_ambito(df, season, liga)
    if d.empty:
        return "Ningún jugador con datos defensivos de FBref cumple los filtros.", None

    top = d.loc[d["recoveries90"].idxmax()]
    fija = (f"En {ambito}, el que más pelota recupera es **{top['player']}** "
            f"({top['team']}) con {_fmt(top['recoveries90'])} por 90', contra una "
            f"media de {_fmt(d['recoveries90'].mean())}.")

    # El dato que salta: el mayor desajuste entre lo mucho que recupera y lo poco
    # que falta. Se compara por percentil dentro del ámbito —no por el cociente
    # recuperaciones/faltas— porque ese cociente se dispara con quien casi no
    # falta, y premiaría a un delantero que ni recupera ni comete faltas.
    if len(d) < 5:
        return fija, None
    limpio = (d["recoveries90"].rank(pct=True) - d["fouls90"].rank(pct=True))
    i = limpio.idxmax()
    e = d.loc[i]
    salta = (f"El que mejor combina las dos cosas es **{e['player']}** "
             f"({e['team']}): {_fmt(e['recoveries90'])} recuperaciones por 90' con "
             f"solo {_fmt(e['fouls90'])} faltas.")
    j = limpio.idxmin()
    o = d.loc[j]
    salta += (f" En el extremo opuesto, **{o['player']}** ({o['team']}) comete "
              f"{_fmt(o['fouls90'])} faltas por 90' y recupera "
              f"{_fmt(o['recoveries90'])}.")
    return fija, salta


def disputar_que_mirar():
    return ("Arriba a la derecha, los que hacen las dos cosas: van al choque y además se "
            "anticipan.\n\n"
            "Un aviso: buena parte de la distancia entre dos puntos es **la posición y el "
            "equipo**, no el jugador. Un central intercepta más que un extremo porque "
            "juega donde llegan los pases, no porque lea mejor el juego.")


def disputar_por_que(df):
    d = df[df["tkl_w90"].notna()]
    r = d["tkl_w90"].corr(d["interceptions90"])
    return (
        f"Lo primero es comprobar que los dos ejes no sean la misma medida dos veces: "
        f"los dos crecen con el volumen defensivo. **Correlacionan {_fmt(r)}** sobre "
        f"las {miles(len(d))} jugador-temporadas de todas las temporadas: "
        f"{_cuanto(r)} (comparten un {r ** 2 * 100:.0f}% de su variación). Por eso "
        f"van cruzadas y no sumadas; sumadas son el eje X de \"Recuperar vs. cortar con "
        f"falta\", que es la otra pregunta.\n\n"
        f"Se usan **entradas ganadas** y no entradas intentadas porque FBref dejó de "
        f"publicar las segundas (y con ellas los duelos, los bloqueos y los "
        f"despejes). Lo que queda mide una entrada que terminó con la pelota "
        f"recuperada.\n\n"
        f"Como en la otra defensiva, las columnas son de **FBref** y van sobre "
        f"minutos de FBref; {_corte()} usa los de Understat."
        + _parrafo(_quiebre_intercepciones(d))
    )


def disputar(df, season, liga=None):
    d, ambito = _defensa_ambito(df, season, liga)
    if d.empty:
        return "Ningún jugador con datos defensivos de FBref cumple los filtros.", None

    entrador = d.loc[d["tkl_w90"].idxmax()]
    lector = d.loc[d["interceptions90"].idxmax()]
    fija = (f"En {ambito}, el que más entradas gana es **{entrador['player']}** "
            f"({_fmt(entrador['tkl_w90'])} por 90') y el que más intercepta, "
            f"**{lector['player']}** ({_fmt(lector['interceptions90'])} por 90').")

    if len(d) < 5:
        return fija, None
    # Quién está más lejos de hacer las dos cosas por igual: el percentil de un
    # eje menos el del otro. Es la misma regla que usa "Perfil ofensivo" para
    # encontrar al más completo, mirando al revés.
    rx, ry = d["tkl_w90"].rank(pct=True), d["interceptions90"].rank(pct=True)
    completo = d.loc[(rx + ry).idxmax()]
    salta = (f"El más completo de los dos lados es **{completo['player']}** "
             f"({completo['team']}), con {_fmt(completo['tkl_w90'])} entradas y "
             f"{_fmt(completo['interceptions90'])} intercepciones por 90'. "
             + _frase_ambos(d["tkl_w90"], d["interceptions90"]))
    return fija, salta


# --------------------------------------------------------------------------
# Perfil de dos fases — producción esperada vs. recuperaciones
# --------------------------------------------------------------------------
#
# La única gráfica de la sección con un eje de cada fuente: la producción sale
# de Understat y las recuperaciones de FBref. Lo que la sostiene es que el
# compromiso entre las dos fases NO es universal — vive en el mediocampo y
# desaparece en la defensa— y eso solo se ve cruzándolas.

def dos_fases_que_mirar():
    return ("Abajo a la derecha, el atacante puro: pesa en el área rival y no aparece en "
            "la propia. Arriba a la izquierda, el recuperador puro. **Arriba a la "
            "derecha**, los que hacen las dos cosas.\n\n"
            "Aquí el filtro de posición es parte del análisis: la nube entera está "
            "ordenada por puesto antes que por jugador, y la relación entre los dos ejes "
            "**cambia mucho según el puesto** (los números están en \"Por qué estas "
            "variables\").")


def dos_fases_por_que(df):
    r = df["xga90"].corr(df["recoveries90"])
    partes = []
    if "posicion" in df.columns:
        for pos, g in df.groupby("posicion", observed=True):
            # Con pocos jugadores la correlación es ruido. Y un puesto que no
            # participa de una de las dos fases no puede tener un compromiso
            # entre ellas: los porteros producen 0.00 de xG+xA, así que su
            # correlación es un número sin contenido. Se los descarta por el
            # dato —producción prácticamente nula— y no por el nombre del
            # puesto, que es lo que se mantiene solo si mañana cambia.
            if len(g) < 100 or g["xga90"].mean() < 0.01:
                continue
            partes.append(f"**{pos.lower()}s** {_fmt(g['xga90'].corr(g['recoveries90']))}")
    detalle = (f" Y no es igual en toda la cancha: {', '.join(partes)}." if partes else "")
    return (
        f"Los dos ejes suman lo que sus gráficas hermanas separan. El horizontal "
        f"junta xG90 y xA90 —que \"Perfil ofensivo\" cruza— y el vertical, entradas "
        f"e intercepciones, que \"Perfil defensivo\" cruza. Acá la pregunta no es "
        f"qué tipo de aporte hace en cada área sino **en cuál de las dos pesa**, y "
        f"para eso cada mitad tiene que ser un solo número.\n\n"
        f"Sobre las {miles(len(df))} observaciones los dos ejes correlacionan {_fmt(r)}: "
        f"negativo, o sea que hay un compromiso real —producir más arriba va con "
        f"recuperar menos atrás— pero flojo, apenas un {r ** 2 * 100:.0f}% de "
        f"variación compartida, que es lo que deja sitio para los que se salen de "
        f"la regla.{detalle} En la defensa el compromiso **no existe**: un central "
        f"que aporta arriba no recupera menos por eso. Donde sí existe es en el "
        f"mediocampo, que es exactamente donde se discute si un jugador \"llega\" o "
        f"\"corre\".\n\n"
        f"Cada eje sale de una fuente: la producción esperada la publica Understat "
        f"y las recuperaciones, FBref. {_corte().capitalize()} usa los minutos de "
        f"Understat."
        # El eje vertical incluye intercepciones, así que le toca el mismo aviso
        # que a las otras dos defensivas, en corto.
        + _parrafo(_quiebre_intercepciones(df, corto=True))
    )


def dos_fases(df, season, liga=None):
    d, ambito = _defensa_ambito(df, season, liga)
    if d.empty:
        return "Ningún jugador con datos de las dos fases cumple los filtros.", None

    arriba = d.loc[d["xga90"].idxmax()]
    atras = d.loc[d["recoveries90"].idxmax()]
    fija = (f"En {ambito}, el que más produce arriba es **{arriba['player']}** "
            f"({_fmt(arriba['xga90'])} de xG+xA por 90') y el que más recupera "
            f"atrás, **{atras['player']}** ({_fmt(atras['recoveries90'])} por 90').")

    if len(d) < 5:
        return fija, None
    # El más completo por suma de percentiles, misma regla que "Perfil ofensivo"
    # usa para el todocampo.
    rx, ry = d["xga90"].rank(pct=True), d["recoveries90"].rank(pct=True)
    completo = d.loc[(rx + ry).idxmax()]
    # El puesto puede faltar (quien no cruzó por nombre con fbref). Se comprueba
    # que sea texto en vez de con `pd.isna`: este módulo no importa pandas a
    # propósito — recibe los datos ya calculados y solo arma frases.
    puesto = completo.get("posicion")
    quien = f"{completo['player']}** ({completo['team']}"
    quien += f", {puesto.lower()})" if isinstance(puesto, str) and puesto else ")"
    salta = (f"El que mejor pesa en las dos es **{quien}: "
             f"{_fmt(completo['xga90'])} de producción y "
             f"{_fmt(completo['recoveries90'])} recuperaciones por 90'. "
             + _frase_ambos(d["xga90"], d["recoveries90"]))
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
    """Miles con coma ("230,323"), como en México: el punto queda para los decimales."""
    return f"{int(n):,}"


def tiros_que_mirar():
    return (
        "Muestra de dónde se tira en las 5 ligas con un mapa que mira hacia la portería: la línea de fondo es el "
        "borde de arriba y los rectángulos son las áreas grande y chica.\n"
        "El color reparte el 100% de los tiros que ves entre celdas de 2×2 m, así que una celda oscura es una parte "
        "grande del total y no «muchos tiros». Con «Ver», cada punto es un remate de un jugador o equipo: lleno si "
        "fue gol y más grande cuanto más valía.")


def tiros_por_que(n_mapa, n_penales, n_fuera):
    return (
        f"**Los penales quedan fuera** ({miles(n_penales)} en todas las temporadas del mapa). "
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


# --------------------------------------------------------------------------
# Creación de juego (Jugadores): pases clave, construcción y centros
# --------------------------------------------------------------------------

def _ambito(df, season, liga):
    """La temporada elegida, filtrada por liga si hay una, y cómo nombrarla."""
    d = df[df["temporada"] == season]
    if liga and liga != LIGA_TODAS:
        return d[d["liga"] == liga], liga
    return d, "las 5 ligas"


def _lideres(d, col_a, col_b, nombre, fmt_a, fmt_b, que_a, que_b, equipo="team"):
    """La frase fija de las vistas de dos tasas: quién lidera cada eje, o quién
    lidera los dos si es la misma persona."""
    a, b = d.loc[d[col_a].idxmax()], d.loc[d[col_b].idxmax()]
    if a[nombre] == b[nombre]:
        return (f"**{a[nombre]}** ({a[equipo]}) lidera los dos ejes: {que_a} "
                f"({fmt_a(a[col_a])}) y {que_b} ({fmt_b(a[col_b])}).")
    # No `.capitalize()`: pondría el resto en minúscula y "xG" saldría "xg".
    mayus = lambda t: t[0].upper() + t[1:]
    return (f"{mayus(que_a)}: **{a[nombre]}** ({a[equipo]}, {fmt_a(a[col_a])}). "
            f"{mayus(que_b)}: **{b[nombre]}** ({b[equipo]}, {fmt_b(b[col_b])}).")


def pases_clave_que_mirar():
    return ("Lo que enseña es la **calidad** y no solo el volumen: por debajo de la nube "
            "están los que dan muchos pases clave de poco peligro (pases largos, tiros de "
            "lejos de sus compañeros); por encima, los que dan pocos pero que acaban en "
            "ocasiones claras. Como casi siempre, la posición pesa: el filtro de la "
            "cancha deja comparar entre iguales.")


def pases_clave_por_que(df):
    r = df["kp90"].corr(df["xA90"])
    return (
        f"El **pase clave** cuenta cuántos pases terminaron en un tiro, sin importar "
        f"qué tan bueno fue ese tiro; el **xA** le pone precio a cada uno según la "
        f"probabilidad de gol del remate que habilitó. Son dos preguntas distintas: "
        f"cuánto crea y qué tan peligroso es lo que crea.\n\n"
        f"Correlacionan {_fmt(r)}: {_cuanto(r)} (comparten el {r ** 2 * 100:.0f}% de "
        f"su variación). Lo que queda es la diferencia entre dar muchos pases clave "
        f"y darlos buenos. Ambos van por 90 minutos para que el suplente que rinde "
        f"en poco tiempo no quede enterrado, y con {_corte()} para que unos pocos "
        f"minutos con un pase afortunado no den una tasa imposible."
    )


def pases_clave(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "kp90", "xA90", "player", lambda v: _fmt(v, 1), _fmt,
        "más pases clave por 90'", "más xA por 90'")
    if len(d) < 5:
        return fija, None
    # Peligro por pase clave: solo entre quienes dan pases clave seguido, porque
    # con uno cada tanto el cociente es ruido puro.
    # Con menos de 10 pases clave en la temporada el cociente también es ruido.
    frecuentes = d[(d["kp90"] >= d["kp90"].median()) & (d["kp90"] > 0)
                   & (d["key_passes"] >= 10)].copy()
    if len(frecuentes) < 3:  # p. ej. solo porteros: casi nadie da pases clave
        return fija, None
    frecuentes["por_pase"] = frecuentes["xA90"] / frecuentes["kp90"]
    mejor = frecuentes.loc[frecuentes["por_pase"].idxmax()]
    salta = (f"Entre los que dan pases clave seguido (10 o más en la temporada), el que más peligro saca de cada "
             f"uno es **{mejor['player']}**: {_fmt(mejor['por_pase'])} de xA por pase "
             f"clave, contra {_fmt(frecuentes['por_pase'].mean())} del grupo.")
    return fija, salta


def construir_que_mirar():
    return (
        "Separa a quien arma las jugadas de tiro de quien las termina, por 90 minutos. La construcción, en el eje "
        "horizontal, es el xG de las jugadas de tiro en las que el jugador participa sin tirar ni dar el último pase.\n"
        "La producción, en el vertical, suma el xG de sus tiros y el xA de sus pases, o sea, lo que genera de forma "
        "directa. Las líneas marcan el 20% más alto de cada eje.")


def construir_por_que(df):
    r = df["xgbuild90"].corr(df["xga90"])
    return (
        f"El **xG de construcción** suma el valor de las jugadas que acabaron en tiro y en las que el jugador participó "
        f"**sin tirar ni dar el último pase**.\n\n"
        f"Ojo: **depende del equipo**, sobre todo la construcción: quien juega en un equipo que genera mucho xG participa "
        f"en más jugadas con xG, juegue como juegue. Entre defensas y medios el club explica la mayor parte de la "
        f"construcción y bastante menos la producción; aquí no se corrige. La correlación de {_fmt(r)} con todas las "
        f"posiciones juntas ({_cuanto(r)}) sale de mezclar puestos: dentro de una posición, los ejes van más de la mano."
    )


def construir(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "xgbuild90", "xga90", "player", _fmt, _fmt,
        "más construcción por 90'", "más producción directa (xG + xA) por 90'")
    if len(d) < 5:
        return fija, None
    poco = d[d["xga90"] <= d["xga90"].median()]
    c = poco.loc[poco["xgbuild90"].idxmax()]
    salta = (f"El constructor más puro es **{c['player']}**: {_fmt(c['xgbuild90'])} "
             f"de xG de construcción por 90' y solo {_fmt(c['xga90'])} de producción "
             f"directa — está en la mayoría de las jugadas peligrosas de su equipo "
             f"sin que el tiro o el último pase sean suyos.")
    return fija, salta


# --------------------------------------------------------------------------
# Las tres vistas "por 90'" de goles y asistencias (2026-11-19)
# --------------------------------------------------------------------------
#
# xG vs. goles por 90', xA vs. asistencias por 90' y pases clave vs. asistencias por 90'. Las tres usan el corte de
# 900 minutos (`players.MIN_MINUTES_90`): una tasa por 90' con 500 minutos se dispara con un solo gol.

# "Élite": el 30% con más xG por 90' de los que se ven (percentil 70). Tiene que valer lo mismo en `insights.js` (`ELITE_PCT`) y en
# la línea que dibuja la gráfica (`referencia.zonas.pct`, que sale de aquí).
ELITE_PCT = 0.7
# Las líneas punteadas de las demás vistas de dos ejes ("élite" en cada eje, p. ej. el 20% con más pases clave): tiene que
# valer lo mismo en `insights.js` (`LINEA_PCT`) y en `players._promedios`. Las de Corte vs. Cobertura van en el percentil
# 70 de una escala que ya es de percentiles (`LINEA_PERCENTIL`).
LINEA_PCT = 0.8
LINEA_PERCENTIL = 70
MIN_MINUTOS_90 = 900


def _pct_elite():
    """«30%»: lo que queda a la derecha de la línea de la élite (el 30% con más xG)."""
    return f"{round((1 - ELITE_PCT) * 100)}%"


def _corte90():
    return f"El corte de {MIN_MINUTOS_90} minutos (menos en la temporada en curso)"


def xg_goles_90_que_mirar():
    return (
        "Compara los goles que marca cada jugador con los que valían sus ocasiones. En el eje horizontal está el xG, "
        "que suma la probabilidad de gol de cada tiro según desde dónde y cómo se hizo, y en el vertical, los goles "
        "reales, ambos por 90 minutos y sin penales.\n"
        "La diagonal marca el punto en que marcó justo lo esperado, de modo que quien está arriba rinde por encima de "
        "sus ocasiones y quien está abajo, por debajo. La línea vertical separa al 30% de jugadores con más xG.")


def xg_goles_90_por_que(df):
    r = df["npxg90"].corr(df["npg90"])
    dif = (df["npg90"] - df["npxg90"]).mean()
    razon = df["np_goals"].sum() / df["np_xg"].sum()
    return (
        f"El xG suma la probabilidad de gol de cada remate según desde dónde y cómo se hizo; restarlo de los goles deja la "
        f"definición más la suerte, y en una temporada no hay forma de separarlas.\n\n"
        f"Va **por 90 minutos** y **sin penales**: un penal vale cerca de 0.76 de xG y entra casi 8 de cada 10 veces, así "
        f"que quien los tira aparece \"de más\" sin haber definido mejor. {_corte90()} evita que un gol de rebote dé una "
        f"tasa imposible.\n\n"
        f"Los dos ejes correlacionan {_fmt(r)}: {_cuanto(r)}. Estar en la zona de élite dice que genera mucho **esta "
        f"temporada**; marcar menos de lo que genera no es un defecto probado."
        + _frase_persistencia(df, "np_goals", "np_xg", "goles y xG sin penales") +
        f" Además, el xG de Understat suma {'más' if dif < 0 else 'menos'} de lo que entra: en total, los jugadores metieron "
        f"el {razon * 100:.0f}% de su xG, lo que empuja a toda la nube {'por debajo' if dif < 0 else 'por encima'} de la "
        f"diagonal."
    )


def xg_goles_90(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "npxg90", "npg90", "player", _fmt, _fmt,
        "más xG por 90' sin penales", "más goles por 90' sin penales")
    if len(d) < 5:
        return fija, None
    corte = d["npxg90"].quantile(ELITE_PCT)
    elite = d[d["npxg90"] >= corte]
    mas = elite[elite["npg90"] >= elite["npxg90"]]
    menos = elite[elite["npg90"] < elite["npxg90"]]
    salta = (f"El {_pct_elite()} con más xG por 90' son {len(elite)} jugadores (desde {_fmt(corte)}): {len(mas)} "
             f"marcan al menos lo que generan y {len(menos)} marcan menos.")
    if len(menos):
        p = menos.loc[(menos["npg90"] - menos["npxg90"]).idxmin()]
        salta += (f" El que más se queda corto es **{p['player']}**: {_fmt(p['npg90'])} goles contra "
                  f"{_fmt(p['npxg90'])} de xG por 90'.")
    return fija, salta


def xa_asist_90_que_mirar():
    return (
        "Compara las asistencias que da cada jugador con las que valían sus pases. El xA, en el eje horizontal, mide "
        "el peligro de sus pases de gol, es decir, la probabilidad de que el tiro que habilitó termine en gol, y en "
        "el vertical están las asistencias reales, ambas por 90 minutos.\n"
        "Sobre la diagonal, sus compañeros convirtieron más de lo esperado y debajo, menos. La línea vertical separa "
        "al 20% de jugadores con más xA, los que más peligro crean con sus pases.")


def xa_asist_90_por_que(df):
    r = df["xA90"].corr(df["a90"])
    return (
        f"El xA mide **cuánta probabilidad de gol generó el remate que habilitó** el jugador. Por 90' correlaciona "
        f"{_fmt(r)} con las asistencias reales.\n\n"
        f"A diferencia de la gráfica de goles, estar arriba de la diagonal **no dice que hizo algo distinto**: una "
        f"asistencia depende de que otro la meta, así que dice sobre todo que quien remató acertó, o tuvo suerte. Conviene "
        f"leerla como medida de creación (eje horizontal). {_corte90()} evita que una asistencia de rebote dispare la tasa."
        + _frase_persistencia(df, "a", "xA", "asistencias y xA")
    )


def xa_asist_90(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "xA90", "a90", "player", _fmt, _fmt,
        "más xA por 90'", "más asistencias por 90'")
    if len(d) < 5:
        return fija, None
    dif = d["a90"] - d["xA90"]
    arriba, abajo = d.loc[dif.idxmax()], d.loc[dif.idxmin()]
    salta = (f"**{arriba['player']}** es el que más se pasa de su xA ({_sg(dif.max())} asistencias por 90'), y a "
             f"**{abajo['player']}** es a quien más le desperdician ({_sg(dif.min())}). En los dos casos habla "
             f"tanto de ellos como de quienes remataron sus pases.")
    return fija, salta


def pases_asist_que_mirar():
    return (
        "Compara cuántos pases clave da cada jugador con cuántos terminan en asistencia, por 90 minutos. Un pase "
        "clave es el que acaba en tiro y una asistencia, el que acaba en gol, así que toda asistencia cuenta también "
        "como pase clave.\n"
        "El eje horizontal mide cuánto crea el jugador y el vertical cuánto de eso acaba en gol, y las líneas marcan "
        "el 20% más alto de cada uno.")


def pases_asist_por_que(df):
    r = df["kp90"].corr(df["a90"])
    return (
        f"El **pase clave** cuenta los pases que terminaron en tiro, sea gol o no; la **asistencia**, el que termina en "
        f"gol. La distancia entre los dos depende sobre todo de quienes reciben el pase (rematar bien o mal, el portero) y "
        f"en parte de qué tan buenos son los tiros que el pasador genera.\n\n"
        f"Correlacionan {_fmt(r)}: {_cuanto(r)}. Va por 90' y con {_corte90().lower()} para que un suplente no quede "
        f"enterrado ni un pase afortunado dé una tasa imposible. Con una temporada hay mucho azar: pocos pases clave y un "
        f"par de asistencias de más o de menos mueven mucho a un jugador."
    )


def pases_asist(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "kp90", "a90", "player", lambda v: _fmt(v, 1), _fmt,
        "más pases clave por 90'", "más asistencias por 90'")
    if len(d) < 5:
        return fija, None
    corte = d["kp90"].quantile(0.75)
    muchos = d[d["kp90"] >= corte]
    if muchos.empty:
        return fija, None
    p = muchos.loc[muchos["a90"].idxmin()]
    salta = (f"Entre el 25% que más pases clave da, al que menos le convierten es **{p['player']}**: "
             f"{_fmt(p['kp90'], 1)} pases clave por 90' y {_fmt(p['a90'])} asistencias.")
    return fija, salta


# --------------------------------------------------------------------------
# Defensa: Corte vs. Cobertura (2026-11-19)
# --------------------------------------------------------------------------
#
# Reemplaza a las dos vistas defensivas anteriores. Percentiles de 0 a 100 entre los defensas con el corte de 900
# minutos, dentro de cada temporada: corte = promedio de los percentiles de entradas ganadas y faltas cometidas;
# cobertura = percentil de intercepciones. Las cuentan de FBref; despejes, bloqueos y duelos no existen en nuestros datos.

def cover_stopper_que_mirar():
    return (
        "Ubica a cada defensa frente a los de su misma temporada, en percentiles de 0 a 100. El corte, en el eje "
        "vertical, promedia dos percentiles, entradas ganadas y faltas por 90 minutos, y refleja qué tanto va al "
        "choque.\n"
        "La cobertura, en el horizontal, es el percentil de intercepciones por 90 minutos y refleja qué tanto lee el "
        "pase y se anticipa. Las líneas están en el percentil 70, así que quien las supera destaca en esa faceta.")


def cover_stopper_por_que(df):
    d = df[df["pct_stopper"].notna()]
    r = d["pct_stopper"].corr(d["pct_cover"])
    return (
        f"Es la idea de los dos perfiles de defensa, el que sale a disputar y el que se queda a leer el juego, con lo que "
        f"hay: de FBref solo sobreviven **entradas ganadas, intercepciones y faltas**; **no hay despejes, bloqueos ni "
        f"duelos aéreos**, que suelen ser lo que más separa a un central de otro. Es una aproximación, no el perfil "
        f"completo.\n\n"
        f"El **corte** es el promedio de los percentiles de entradas ganadas y de faltas por 90' (las faltas cuentan porque "
        f"acompañan al choque); la **cobertura**, el percentil de intercepciones por 90'. Los percentiles se sacan "
        f"**dentro de cada temporada** entre los defensas con {MIN_MINUTOS_90} minutos o más (menos en la que va en "
        f"curso). Los dos ejes correlacionan {_fmt(r)}: {_cuanto(r)}."
        + _parrafo(_quiebre_intercepciones(d))
    )


def cover_stopper(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "pct_stopper", "pct_cover", "player", lambda v: _fmt(v, 0), lambda v: _fmt(v, 0),
        "más corte", "más cobertura")
    if len(d) < 5:
        return fija, None
    stop, cov = d["pct_stopper"] > LINEA_PERCENTIL, d["pct_cover"] > LINEA_PERCENTIL
    a, b, c = int((stop & ~cov).sum()), int((cov & ~stop).sum()), int((stop & cov).sum())
    e = d.loc[(d["pct_stopper"] + d["pct_cover"]).idxmax()]
    salta = (f"De {len(d)} defensas, {a} se inclinan al corte, {b} a la cobertura, {c} a los dos y {len(d) - a - b - c} a "
             f"ninguno (las líneas están en el percentil {LINEA_PERCENTIL}). El más completo es **{e['player']}** ({e['team']}): "
             f"{_fmt(e['pct_stopper'], 0)} de corte y {_fmt(e['pct_cover'], 0)} de cobertura.")
    return fija, salta


def centros_que_mirar():
    return ("La nube sube con el volumen pero con mucha dispersión: abajo a la derecha "
            "están los que centran de forma constante con poco peligro (la mayoría de los "
            "centros no encuentra a nadie); arriba, los que generan ocasión por otras "
            "vías además del centro. Casi todo lo de la derecha son laterales y extremos, "
            "así que conviene filtrar por posición.")


def centros_por_que(df):
    r = df["crosses90"].corr(df["xA90"])
    return (
        f"Los **centros** vienen de FBref (que sigue publicándolos) y el **xA** de "
        f"Understat, así que son dos fuentes independientes midiendo cosas "
        f"cercanas. Correlacionan {_fmt(r)}: {_cuanto(r)}. El centro es una de las "
        f"formas de crear ocasión, y hay otras.\n\n"
        f"Un centro cuenta igual salga bien o mal, y el xA solo cuenta los pases "
        f"que terminaron en tiro; por eso un jugador puede estar muy a la derecha "
        f"y bajo en el eje vertical sin que eso diga que centra mal — la "
        f"diferencia es cuánto de su volumen encuentra rematador."
    )


def centros(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    fija = f"En {ambito}: " + _lideres(
        d, "crosses90", "xA90", "player", lambda v: _fmt(v, 1), _fmt,
        "quien más centra por 90'", "quien más xA por 90'")
    if len(d) < 5:
        return fija, None
    muchos = d[d["crosses90"] >= d["crosses90"].quantile(0.75)]
    if muchos.empty:
        return fija, None
    p = muchos.loc[muchos["xA90"].idxmin()]
    salta = (f"Entre el 25% que más centra, el que menos peligro genera es "
             f"**{p['player']}**: {_fmt(p['crosses90'], 1)} centros por 90' y "
             f"{_fmt(p['xA90'])} de xA — volumen que casi no se convierte en "
             f"ocasión.")
    return fija, salta


# --------------------------------------------------------------------------
# Equipos: las cuatro vistas de ataque y defensa, con xG de Understat
# --------------------------------------------------------------------------
#
# xG y goles de cada equipo POR PARTIDO y SIN PENALES (ni autogoles), de `web/charts/xg_equipos.py`.
# Las vistas viejas medían con proxies de FBref (tiros a puerta, asistencias) que casi no dicen nada:
# el azar explica ~70-90% de la dispersión de los goles por tiro a puerta entre equipos, y las
# asistencias son el gol con otra etiqueta.
#
# Las cifras de los textos "por qué" salen de los datos, con las temporadas CERRADAS (la que va en
# curso tiene 6 a 9 partidos por equipo y mete mucho ruido). Lo que se repite de una temporada a la
# siguiente es la medida de cuánto es del equipo y cuánto del azar.

XG_FAV, XG_CON, XG_DIF = "xg_fav", "xg_con", "xg_dif"
GOL_FAV, GOL_CON = "gol_fav", "gol_con"
PARTIDOS_XG, PARTIDOS_FBREF = "xg_partidos", "ov_Playing Time_MP"
MIN_CERRADA = 30   # partidos: la misma regla con la que `site_utils.temporadas_en_curso` marca las que van en curso


def _sg(v, dec=2):
    """Con el signo a la vista en los positivos ("+0.45", "-0.12"). Mismo texto que `sg` de insights.js."""
    return f"{v:+.{dec}f}"


def _cerradas_eq(df):
    """Las filas de las temporadas cerradas: aquellas en las que algún equipo ya jugó 30 partidos o más."""
    maximos = df.groupby("temporada")[PARTIDOS_FBREF].max()
    return df[df["temporada"].isin(maximos[maximos >= MIN_CERRADA].index)]


def _persistencia_equipos(df, valor):
    """Cuánto se repite `valor` (una serie con el índice de `df`) de una temporada cerrada a la siguiente:
    la correlación, por cada par de temporadas cerradas seguidas, entre los equipos que están en las dos.
    Devuelve `(menor, mayor, menos equipos, más equipos)` o None."""
    c = _cerradas_eq(df)
    v = valor.loc[c.index]
    temporadas = sorted(c["temporada"].unique())
    por_temp = {t: v[c["temporada"] == t].set_axis(c.loc[c["temporada"] == t, "Squad"]) for t in temporadas}
    rs, ns = [], []
    for a, b in zip(temporadas, temporadas[1:]):
        comun = por_temp[a].index.intersection(por_temp[b].index)
        if len(comun) >= 30:
            rs.append(por_temp[a][comun].corr(por_temp[b][comun]))
            ns.append(len(comun))
    return (min(rs), max(rs), min(ns), max(ns)) if rs else None


def _entre(p):
    """"entre 0.11 y 0.20" para un resultado de `_persistencia_equipos`."""
    lo, hi, n_lo, n_hi = p
    return f"entre {_fmt(lo)} y {_fmt(hi)}"


def _se_repite(p):
    """Qué tanto se repite, con las bandas de `_cuanto` pero sobre el valor más alto de los pares."""
    hi = max(abs(p[0]), abs(p[1]))
    if hi < 0.3:
        return "Casi nada se repite."
    if hi < 0.6:
        return "Se repite en parte."
    return "Se repite bastante."


# --- Goles vs. xG (eficiencia-definicion) ---------------------------------------------------

def definicion_que_mirar():
    return (
        "Compara los goles que marca cada equipo con los que valían sus ocasiones, por partido y sin penales. El eje "
        "horizontal es el xG, las ocasiones que crea, y el vertical, los goles reales.\n"
        "La diagonal marca el punto en que el equipo marca justo lo esperado: sobre ella marca más de lo que valían "
        "sus ocasiones y debajo, menos, así que lo que cuenta es la distancia a esa línea.")


def definicion_por_que(df):
    c = _cerradas_eq(df)
    r2 = c[XG_FAV].corr(c[GOL_FAV]) ** 2 * 100
    persist = _persistencia_equipos(df, df[GOL_FAV] - df[XG_FAV])
    p2 = (f"El xG explica el {r2:.0f}% de la variación de los goles por partido entre equipos "
          f"({miles(len(c))} equipos-temporada cerrados). Lo que queda es la distancia a la diagonal")
    p2 += (f". De una temporada cerrada a la siguiente, la de un mismo equipo correlaciona {_entre(persist)}. Unas cuatro "
           f"quintas partes de esa distancia es azar de los partidos, y por eso se repite poco aunque exista un efecto "
           f"real del equipo: una distancia grande en una temporada suele acercarse a cero en la siguiente.") if persist else "."
    # cuánto de su xG meten los equipos, en la primera y la última temporada cerrada
    tot = (c.assign(g=c[GOL_FAV] * c[PARTIDOS_XG], x=c[XG_FAV] * c[PARTIDOS_XG])
           .groupby("temporada")[["g", "x"]].sum())
    razon = tot["g"] / tot["x"]
    calibra = f"El xG de Understat suma {'más' if razon.mean() < 1 else 'menos'} de lo que entra"
    if len(razon) > 1:
        calibra += (f": en {razon.index[0]} los equipos metieron el {razon.iloc[0] * 100:.0f}% de su xG y en "
                    f"{razon.index[-1]}, el {razon.iloc[-1] * 100:.0f}%.")
    else:
        calibra += "."
    return (
        f"El xG suma **cuántas y qué tan buenas son las ocasiones**. Restarlo de los goles deja la definición, la suerte y "
        f"el error del propio xG, y en una temporada no hay forma de separarlas.\n\n"
        f"{p2}\n\n"
        f"{calibra} Va por partido porque no todas las ligas juegan las mismas jornadas (la Bundesliga siempre 34, la "
        f"Ligue 1 desde 2023-24, las otras tres 38); los penales y los autogoles quedan fuera."
    )


def definicion(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    top = d.loc[d[GOL_FAV].idxmax()]
    fija = (f"En {ambito}, **{top['Squad']}** es el que más goles mete por partido "
            f"({_fmt(top[GOL_FAV])}) con {_fmt(top[XG_FAV])} de xG.")
    if len(d) < 4:
        return fija, None
    dif = d[GOL_FAV] - d[XG_FAV]
    arriba, abajo = d.loc[dif.idxmax()], d.loc[dif.idxmin()]
    mx, mn = dif.max(), dif.min()
    mas = (f"El que más superó su xG es **{arriba['Squad']}** ({_sg(mx)} goles por partido)" if mx > 0
           else f"Ninguno superó su xG: el que más cerca quedó es **{arriba['Squad']}** "
                f"({_fmt(mx)} goles por partido)")
    menos = (f"y el que más se quedó corto, **{abajo['Squad']}** ({_fmt(mn)})." if mn < 0
             else f"y todos lo superaron: el que menos, **{abajo['Squad']}** ({_sg(mn)}).")
    salta = (f"{mas} {menos} Una diferencia así se repite poco de una temporada a la siguiente.")
    return fija, salta


# --- Ocasiones a favor y en contra (creacion) -----------------------------------------------

def creacion_que_mirar():
    return (
        "Compara lo que cada equipo crea con lo que concede, medido en xG por partido y sin penales. El eje "
        "horizontal es el xG que genera su ataque y el vertical, el que permite a sus rivales.\n"
        "El eje vertical va al revés: cuanto más arriba está un equipo, menos xG concede, así que arriba a la derecha "
        "quedan los que dominan las ocasiones. Las líneas están en el promedio de cada eje y el xG cuenta ocasiones, "
        "no goles.")


def creacion_por_que(df):
    c = _cerradas_eq(df)
    r = c[XG_FAV].corr(c[XG_CON])
    p_xg = _persistencia_equipos(df, df[XG_DIF])
    p_gol = _persistencia_equipos(df, df[GOL_FAV] - df[GOL_CON])
    p2 = (f"Los dos ejes correlacionan {_fmt(r)} sobre {miles(len(c))} equipos-temporada cerrados: "
          f"{_cuanto(r)}.")
    if r < -0.3:
        p2 += " Los que más crean tienden a conceder menos, pero con mucho margen."
    if p_xg and p_gol:
        p2 += (f" De una temporada cerrada a la siguiente, la diferencia de xG por partido de un mismo equipo (lo que crea "
               f"menos lo que concede) correlaciona {_entre(p_xg)}, y la de goles, {_entre(p_gol)}.")
    return (
        f"Cruza lo que un equipo crea con lo que deja crear: xG de Understat por partido y sin penales, así que cuenta "
        f"ocasiones y no goles, que dependen más del azar.\n\n"
        f"{p2}"
    )


def creacion(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    crea, cede = d.loc[d[XG_FAV].idxmax()], d.loc[d[XG_CON].idxmin()]
    if crea["Squad"] == cede["Squad"]:
        fija = (f"En {ambito}, **{crea['Squad']}** es el que más ocasiones crea y el que menos concede: "
                f"{_fmt(crea[XG_FAV])} de xG a favor y {_fmt(crea[XG_CON])} en contra por partido.")
    else:
        fija = (f"En {ambito}, **{crea['Squad']}** es el que más ocasiones crea "
                f"({_fmt(crea[XG_FAV])} de xG por partido) y **{cede['Squad']}** el que menos concede "
                f"({_fmt(cede[XG_CON])}).")
    if len(d) < 4:
        return fija, None
    dif = d[XG_DIF]
    mejor, peor = d.loc[dif.idxmax()], d.loc[dif.idxmin()]
    salta = (f"El que más domina las ocasiones es **{mejor['Squad']}**: crea {_fmt(mejor[XG_FAV])} y "
             f"concede {_fmt(mejor[XG_CON])} por partido ({_sg(dif.max())}). En el otro extremo, "
             f"**{peor['Squad']}** crea {_fmt(peor[XG_FAV])} y concede {_fmt(peor[XG_CON])} "
             f"({_sg(dif.min())}).")
    return fija, salta


# --- Goles recibidos vs. xG en contra (defensa) ---------------------------------------------

def defensa_que_mirar():
    return (
        "Compara los goles que recibe cada equipo con los que valían las ocasiones que concede, por partido y sin "
        "penales. El eje horizontal es el xG en contra y el vertical, los goles recibidos.\n"
        "Los dos ejes van al revés, así que cuanto más arriba y a la derecha, menos ocasiones concede y menos goles "
        "recibe. Sobre la diagonal el equipo recibe menos goles de los que valían esas ocasiones; debajo, más.")


def defensa_por_que(df):
    c = _cerradas_eq(df)
    r2 = c[XG_CON].corr(c[GOL_CON]) ** 2 * 100
    persist = _persistencia_equipos(df, df[GOL_CON] - df[XG_CON])
    p2 = (f"El xG en contra explica el {r2:.0f}% de la variación de los goles recibidos por partido entre equipos "
          f"({miles(len(c))} equipos-temporada cerrados).")
    if persist:
        p2 += (f" De la distancia a la diagonal, de una temporada cerrada a la siguiente, la diferencia de un mismo equipo "
               f"correlaciona {_entre(persist)}. {_se_repite(persist)}")
    return (
        f"Los goles recibidos juntan cuántas ocasiones concede el equipo, qué tan buenas son y qué pasa con ellas (portero, "
        f"bloqueos, suerte). El eje horizontal mide las dos primeras (xG en contra de Understat, por partido y sin "
        f"penales); la distancia a la diagonal, lo demás.\n\n"
        f"{p2} Para juzgar a un portero haría falta el xG de postremate, que estos datos no traen. Va por partido porque "
        f"no todas las ligas juegan las mismas jornadas (la Bundesliga siempre 34, la Ligue 1 desde 2023-24, las otras tres "
        f"38)."
    )


def defensa(df, season, liga=None):
    d, ambito = _ambito(df, season, liga)
    menos_g, menos_x = d.loc[d[GOL_CON].idxmin()], d.loc[d[XG_CON].idxmin()]
    if menos_g["Squad"] == menos_x["Squad"]:
        fija = (f"En {ambito}, **{menos_g['Squad']}** es el que menos goles recibe "
                f"({_fmt(menos_g[GOL_CON])} por partido) y también el que menos xG concede "
                f"({_fmt(menos_g[XG_CON])}).")
    else:
        fija = (f"En {ambito}, **{menos_g['Squad']}** es el que menos goles recibe "
                f"({_fmt(menos_g[GOL_CON])} por partido) y **{menos_x['Squad']}** el que menos xG concede "
                f"({_fmt(menos_x[XG_CON])}).")
    if len(d) < 4:
        return fija, None
    dif = d[GOL_CON] - d[XG_CON]
    i = dif.abs().idxmax()
    e, delta = d.loc[i], dif[i]
    sentido = "más" if delta > 0 else "menos"
    salta = (f"El que más se aleja de la diagonal es **{e['Squad']}**: concede {_fmt(e[XG_CON])} de xG por "
             f"partido y recibe {_fmt(e[GOL_CON])} goles, {_fmt(abs(delta))} {sentido} de lo que decían las "
             f"ocasiones. Ahí cuentan juntos el portero, la defensa y la suerte.")
    return fija, salta


# --- Cantidad vs. calidad de los tiros y Local vs. visitante ---------------------------------
# Los textos fijos de estas dos vistas (`web/charts/equipos_tiros.py` calcula las columnas). El texto «Con estos filtros»
# de las dos NO tiene gemelo aquí: vive solo en `insights.js` (`cantidadCalidad` y `localVisitante`) y está fuera de la
# prueba de paridad, como `lecturaEntidad` de `tiros.js`.

TIROS_PP, XG_TIRO = "tiros_pp", "xg_tiro"
DIF_LOCAL, DIF_VISITA = "xg_dif_local", "xg_dif_visita"
PARTIDOS_LOCAL, PARTIDOS_VISITA = "partidos_local", "partidos_visita"


def _frase_calibra(df):
    """Una frase con lo que de verdad pasó con el xG de Understat en las temporadas cerradas: cuánto de lo que sumaba
    metieron los equipos (sin penales)."""
    c = _cerradas_eq(df)
    goles, xg = (c[GOL_FAV] * c[PARTIDOS_XG]).sum(), (c[XG_FAV] * c[PARTIDOS_XG]).sum()
    return (f"El xG de Understat suma {'más' if goles < xg else 'menos'} de lo que entra: en las temporadas cerradas "
            f"los equipos metieron el {goles / xg * 100:.0f}% de lo que sumaba su xG sin penales.")


def _frase_en_curso(df, extra=""):
    """Qué pasa con la temporada que va en curso (6 a 9 partidos por equipo): vacía si no hay ninguna."""
    resto = df.drop(_cerradas_eq(df).index)
    if resto.empty:
        return ""
    mp = resto[PARTIDOS_FBREF]
    cuantos = f"{int(mp.min())}" if mp.min() == mp.max() else f"de {int(mp.min())} a {int(mp.max())}"
    return (f" En la temporada que va en curso cada equipo lleva {cuantos} partidos{extra}: se dibuja, pero no se "
            f"concluye nada de ella.")


def cantidad_calidad_que_mirar():
    return (
        "Muestra cuánto tira cada equipo y qué tan buenos son esos tiros, por partido y sin penales. El eje "
        "horizontal son los tiros por partido y el vertical, el xG por tiro, que es la calidad promedio de sus "
        "remates.\n"
        "Si multiplicas los dos ejes obtienes el xG a favor por partido de «Ocasiones a favor y en contra», es decir, "
        "la misma producción de ocasiones vista como volumen por calidad. Las líneas marcan el 20% más alto de cada "
        "eje.")


def cantidad_calidad_por_que(df):
    c = _cerradas_eq(df)
    r = c[TIROS_PP].corr(c[XG_TIRO])
    p_n, p_q = _persistencia_equipos(df, df[TIROS_PP]), _persistencia_equipos(df, df[XG_TIRO])
    p2 = f"Los dos ejes correlacionan {_fmt(r)} sobre {miles(len(c))} equipos-temporada cerrados: {_cuanto(r)}."
    if r >= 0.3:
        p2 += " Los que más tiran tienden a tirar mejor, pero hay equipos que tiran mucho sin calidad."
    if p_n and p_q:
        mas = ("más" if (p_n[0] + p_n[1]) > (p_q[0] + p_q[1]) else "menos")
        p2 += (f" De una temporada cerrada a la siguiente, los tiros por partido de un mismo equipo correlacionan "
               f"{_entre(p_n)} y el xG por tiro, {_entre(p_q)}: el volumen se repite {mas} que la calidad.")
    return (
        f"Cada tiro trae su xG, la probabilidad de que sea gol según desde dónde y cómo se hizo. El eje horizontal son los "
        f"tiros por partido y el vertical, el xG por tiro: qué tan buenas son, en promedio, las ocasiones que se fabrica. "
        f"Mide qué tipo de tiro elige, no qué tan bien lo remata.\n\n"
        f"{p2}\n\n"
        f"Los tiros son los de Understat, sin penales ni autogoles; cuentan también los que bloquea un defensa, que valen "
        f"poco. {_frase_calibra(df)} Va por partido porque no todas las ligas juegan las mismas jornadas (la Bundesliga "
        f"siempre 34, la Ligue 1 desde 2023-24, las otras tres 38).{_frase_en_curso(df)}"
    )


def local_visitante_que_mirar():
    return (
        "Compara cómo le va a cada equipo de local y de visitante, medido por la diferencia de xG por partido: el xG "
        "que crea menos el que concede, sin penales. El eje horizontal es esa diferencia jugando en casa y el "
        "vertical, jugando fuera.\n"
        "Las líneas están en cero, así que a la derecha y arriba el equipo crea más de lo que concede en esa sede. "
        "Cada punto es un equipo de la temporada elegida y su posición dice cómo le fue en cada una.")


def local_visitante_por_que(df):
    c = _cerradas_eq(df)
    dl, dv = c[DIF_LOCAL], c[DIF_VISITA]
    r = dl.corr(dv)
    efecto = df[DIF_LOCAL] - df[DIF_VISITA]
    p = _persistencia_equipos(df, efecto)
    mejor_casa = (dl > dv).mean() * 100
    p2 = (f"El equipo promedio tiene {_sg(dl.mean())} de diferencia de xG por partido de local y {_sg(dv.mean())} de "
          f"visitante: en un mismo partido, el local supera al visitante en {_fmt((dl.mean() - dv.mean()) / 2)}. El "
          f"{mejor_casa:.0f}% de los {miles(len(c))} equipos-temporada cerrados tiene mejor diferencia de local. Local y "
          f"visitante correlacionan {_fmt(r)}: {_cuanto(r)}, y la mayor parte de lo que separa a un buen equipo de uno malo "
          f"se ve en los dos lados.")
    p3 = ""
    if p:
        hi = max(abs(p[0]), abs(p[1]))
        cierre = ("Depender mucho del estadio en una temporada casi no dice que lo vaya a hacer en la siguiente: es más un "
                  "accidente de la temporada que un rasgo del equipo." if hi < 0.3 else
                  "Una parte de la dependencia del estadio es del equipo y otra de la temporada." if hi < 0.6
                  else "La dependencia del estadio es en buena medida un rasgo del equipo.")
        p3 = (f"\n\nLo que importa para «depende de su estadio» es la diferencia local menos visitante. De una temporada "
              f"cerrada a la siguiente, la de un mismo equipo correlaciona {_entre(p)}. {_se_repite(p)} {cierre}")
    pl = c[[PARTIDOS_LOCAL, PARTIDOS_VISITA]]
    muestra = (f"{int(pl.min().min())}" if pl.min().min() == pl.max().max()
               else f"{int(pl.min().min())} a {int(pl.max().max())}")
    return (
        f"Cada eje es la diferencia de xG por partido (a favor menos en contra, de Understat y sin penales) en los partidos "
        f"de una sede. Las dos sedes enfrentan a los mismos rivales: cada equipo recibe una vez a cada uno y lo visita una "
        f"vez.\n\n"
        f"{p2}{p3}\n\n"
        f"Cada punto promedia {'de ' if 'a' in muestra else ''}{muestra} partidos por sede, poca muestra: el xG se mueve "
        f"mucho de un partido a otro. {_frase_calibra(df)}"
        f"{_frase_en_curso(df, ' y solo unos pocos de cada sede')}"
    )


# --- Distribución por liga -------------------------------------------------------------------

def nivel_liga_equipos_que_mirar():
    return (
        "Muestra qué liga está más arriba y qué tan parejos son sus equipos en la variable que elijas. Cada punto es "
        "un equipo (un clic lo resalta) y la escala vertical es la misma en todas las ligas y temporadas.\n"
        "La banda contiene a la mitad central de los equipos de la liga y la raya marca su mediana: una banda más "
        "ancha significa equipos menos parejos y una raya más alta, un nivel típico mayor.")
