"""
Asistente de Scrabble con Métodos Numéricos
  - Estructura de datos : Trie        (búsqueda eficiente de palabras)
  - Método numérico     : Ajuste de curva por Mínimos Cuadrados
                          (resolución con Eliminación Gaussiana)
  - Diccionario         : ~42,000 palabras españolas (pyspellchecker)

Fundamento:
  En Scrabble existe una relación inversa entre la FRECUENCIA de una letra
  en el idioma español y su PUNTAJE en el juego: las letras más comunes valen
  menos (E=1, A=1) y las más raras valen más (Z=10, X=8, J=8).
  Ajustamos un polinomio de grado 2 a esos datos reales usando mínimos
  cuadrados, obteniendo un modelo continuo del "valor estratégico esperado"
  de cualquier letra según su frecuencia.
  Con ese modelo decidimos:
    - Si la mejor palabra que puedes formar supera el valor estratégico
      promedio de tus fichas → JUEGA.
    - Si no → CAMBIA la ficha cuyo puntaje real se aleja más negativamente
      del valor estimado por la curva (es la ficha que "decepciona" más).
"""
import unicodedata

# ---------------------------------------------------------------------------
# DATOS: puntajes y frecuencias del español
# ---------------------------------------------------------------------------
PUNTAJES = {
    'A': 1, 'E': 1, 'I': 1, 'O': 1, 'U': 1,
    'L': 1, 'N': 1, 'R': 1, 'S': 1, 'T': 1,
    'D': 2, 'G': 2,
    'B': 3, 'C': 3, 'M': 3, 'P': 3,
    'F': 4, 'H': 4, 'V': 4, 'Y': 4,
    'Q': 5,
    'J': 8, 'X': 8, 'Ñ': 8,
    'Z': 10, 'K': 10, 'W': 10,
}

# Frecuencias de aparición en textos en español (porcentaje)
# Fuente: Real Academia Española / estudios de lingüística computacional
FRECUENCIAS = {
    'A': 12.53, 'B': 1.42,  'C': 4.68,  'D': 4.67,  'E': 13.72,
    'F': 0.69,  'G': 1.01,  'H': 0.70,  'I': 6.25,  'J': 0.44,
    'K': 0.01,  'L': 4.97,  'M': 3.16,  'N': 7.01,  'Ñ': 0.31,
    'O': 8.68,  'P': 2.51,  'Q': 0.88,  'R': 6.87,  'S': 7.98,
    'T': 4.63,  'U': 3.93,  'V': 0.90,  'W': 0.01,  'X': 0.22,
    'Y': 0.90,  'Z': 0.52,
}


# ---------------------------------------------------------------------------
# CAPA 1 — TRIE  (estructura de búsqueda eficiente por prefijo)
# ---------------------------------------------------------------------------
class NodoTrie:
    def __init__(self):
        self.hijos: dict = {}
        self.es_fin: bool = False
        self.palabra: str | None = None


class Trie:
    """
    Árbol de prefijos. Encuentra todas las palabras formables con un
    conjunto de fichas usando DFS + poda de ramas inválidas.
    """

    def __init__(self):
        self.raiz = NodoTrie()

    def insertar(self, palabra: str):
        nodo = self.raiz
        for letra in palabra.upper():
            if letra not in nodo.hijos:
                nodo.hijos[letra] = NodoTrie()
            nodo = nodo.hijos[letra]
        nodo.es_fin = True
        nodo.palabra = palabra.upper()

    def buscar_palabras(self, fichas: list[str]) -> list[str]:
        fichas = [f.upper() for f in fichas]
        encontradas: set[str] = set()
        self._dfs(self.raiz, fichas, encontradas)
        return sorted(encontradas, key=lambda w: (-puntaje_palabra(w), -len(w)))

    def _dfs(self, nodo: NodoTrie, fichas_restantes: list[str], encontradas: set[str]):
        if nodo.es_fin and nodo.palabra and len(nodo.palabra) >= 2:
            encontradas.add(nodo.palabra)
        vistas: set[str] = set()
        for i, letra in enumerate(fichas_restantes):
            if letra in vistas:
                continue
            vistas.add(letra)
            if letra in nodo.hijos:
                self._dfs(nodo.hijos[letra], fichas_restantes[:i] + fichas_restantes[i + 1:], encontradas)


def puntaje_palabra(palabra: str) -> int:
    return sum(PUNTAJES.get(c, 0) for c in palabra.upper())


# ---------------------------------------------------------------------------
# CAPA 2 — AJUSTE DE CURVA POR MÍNIMOS CUADRADOS
#
# Dado el conjunto de puntos (frecuencia_letra, puntaje_scrabble) para
# las 27 letras del español, ajustamos el polinomio:
#
#   p(x) = c0 + c1·x + c2·x²
#
# minimizando la suma de errores cuadráticos: Σ [p(xi) - yi]²
#
# Esto equivale a resolver el sistema de ecuaciones normales:
#   (Aᵀ A) · c = Aᵀ · y
#
# donde A es la matriz de Vandermonde.  El sistema se resuelve con
# Eliminación Gaussiana con pivoteo parcial.
# ---------------------------------------------------------------------------

def gauss(A: list[list[float]], b: list[float]) -> list[float]:
    """
    Eliminación Gaussiana con pivoteo parcial.
    Resuelve el sistema A·x = b y retorna x.
    """
    n = len(b)
    # Construir matriz aumentada [A | b]
    M = [A[i][:] + [b[i]] for i in range(n)]

    for col in range(n):
        # Pivoteo parcial: llevar la fila con mayor valor absoluto al frente
        max_fila = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[max_fila] = M[max_fila], M[col]

        pivot = M[col][col]
        if abs(pivot) < 1e-12:
            continue  # columna degenerada, seguir

        # Eliminar hacia adelante
        for fila in range(col + 1, n):
            factor = M[fila][col] / pivot
            for j in range(col, n + 1):
                M[fila][j] -= factor * M[col][j]

    # Sustitución hacia atrás
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = M[i][n]
        for j in range(i + 1, n):
            x[i] -= M[i][j] * x[j]
        if abs(M[i][i]) > 1e-12:
            x[i] /= M[i][i]

    return x


def ajuste_polinomio_grado2(xs: list[float], ys: list[float]) -> tuple[list[float], list[dict]]:
    """
    Ajusta p(x) = c0 + c1·x + c2·x² a los puntos (xs, ys)
    usando mínimos cuadrados.

    Construye la matriz de Vandermonde A y resuelve (AᵀA)·c = Aᵀy
    con eliminación gaussiana.

    Retorna:
        coef     — [c0, c1, c2]
        pasos    — detalle de la construcción del sistema (para mostrar en UI)
    """
    n = len(xs)
    grado = 2
    m = grado + 1  # 3 coeficientes

    # Matriz de Vandermonde A  (n × 3)
    A = [[xs[i] ** j for j in range(m)] for i in range(n)]

    # Ecuaciones normales: AᵀA · c = Aᵀy
    ATA = [
        [sum(A[k][i] * A[k][j] for k in range(n)) for j in range(m)]
        for i in range(m)
    ]
    ATy = [sum(A[k][i] * ys[k] for k in range(n)) for i in range(m)]

    pasos = [
        {
            'nombre': 'Matriz AᵀA',
            'valor': [[round(v, 4) for v in fila] for fila in ATA],
        },
        {
            'nombre': 'Vector Aᵀy',
            'valor': [round(v, 4) for v in ATy],
        },
    ]

    coef = gauss(ATA, ATy)
    return coef, pasos


def evaluar_polinomio(coef: list[float], x: float) -> float:
    """Evalúa p(x) = c0 + c1·x + c2·x²"""
    return sum(c * x ** i for i, c in enumerate(coef))


def calcular_r2(ys: list[float], ys_pred: list[float]) -> float:
    """Coeficiente de determinación R²."""
    media = sum(ys) / len(ys)
    ss_tot = sum((y - media) ** 2 for y in ys)
    ss_res = sum((y - yp) ** 2 for y, yp in zip(ys, ys_pred))
    return 1 - ss_res / ss_tot if ss_tot != 0 else 1.0


# ---------------------------------------------------------------------------
# CAPA 3 — ANÁLISIS DE FICHAS CON EL MODELO
# ---------------------------------------------------------------------------

def analizar_fichas_con_curva(fichas: list[str], coef: list[float]) -> list[dict]:
    """
    Para cada ficha calcula:
      - frecuencia_real : % de aparición en español
      - puntaje_real    : valor Scrabble
      - valor_estimado  : p(frecuencia) según la curva ajustada
      - residuo         : puntaje_real - valor_estimado
                          (negativo → la ficha da menos de lo que la curva predice)
    """
    analisis = []
    for f in fichas:
        freq = FRECUENCIAS.get(f, 0.0)
        pts_real = PUNTAJES.get(f, 0)
        pts_estimado = evaluar_polinomio(coef, freq)
        analisis.append({
            'ficha': f,
            'frecuencia': round(freq, 2),
            'puntaje_real': pts_real,
            'valor_estimado': round(pts_estimado, 3),
            'residuo': round(pts_real - pts_estimado, 3),
        })
    return analisis


# ---------------------------------------------------------------------------
# FUNCIÓN PRINCIPAL
# ---------------------------------------------------------------------------

def recomendar(fichas_str: str, trie: Trie) -> dict:
    """
    Recibe fichas como string separado por espacios (ej: 'A R T E S')
    y devuelve un dict con toda la información de la recomendación.
    """
    fichas = fichas_str.strip().upper().split()

    # ── PASO 1: Trie — buscar palabras posibles ──────────────────────────
    palabras = trie.buscar_palabras(fichas)
    mejor_palabra = palabras[0] if palabras else None
    mejor_puntaje = puntaje_palabra(mejor_palabra) if mejor_palabra else 0

    # ── PASO 2: Ajuste de curva — construir modelo con todos los datos ───
    letras_datos = [(FRECUENCIAS[l], PUNTAJES[l]) for l in FRECUENCIAS if l in PUNTAJES]
    xs = [p[0] for p in letras_datos]
    ys = [p[1] for p in letras_datos]

    coef, pasos_gauss = ajuste_polinomio_grado2(xs, ys)

    # Calidad del ajuste
    ys_pred = [evaluar_polinomio(coef, x) for x in xs]
    r2 = calcular_r2(ys, ys_pred)

    # Puntos para graficar la curva (0% a 14% de frecuencia, 60 puntos)
    puntos_curva = [
        {'x': round(i * 14 / 59, 3), 'y': round(evaluar_polinomio(coef, i * 14 / 59), 3)}
        for i in range(60)
    ]

    # Todos los puntos de datos (para la nube de puntos)
    puntos_datos = [
        {'letra': l, 'x': FRECUENCIAS[l], 'y': PUNTAJES[l]}
        for l in FRECUENCIAS if l in PUNTAJES
    ]

    # ── PASO 3: Analizar fichas con el modelo ────────────────────────────
    analisis_fichas = analizar_fichas_con_curva(fichas, coef)

    # Valor estratégico promedio de la mano según la curva
    umbral = sum(d['valor_estimado'] for d in analisis_fichas) / len(analisis_fichas)

    # Decisión: ¿el mejor puntaje obtenible supera el umbral estratégico?
    vale_jugar = mejor_puntaje > umbral and mejor_palabra is not None

    resultado = {
        'fichas': fichas,
        'palabras': palabras[:10],
        'total_palabras': len(palabras),
        'mejor_palabra': mejor_palabra,
        'mejor_puntaje': mejor_puntaje,
        'ajuste_curva': {
            'coeficientes': [round(c, 6) for c in coef],
            'r2': round(r2, 4),
            'pasos_gauss': pasos_gauss,
            'puntos_curva': puntos_curva,
            'puntos_datos': puntos_datos,
            'umbral': round(umbral, 3),
        },
        'analisis_fichas': analisis_fichas,
        'vale_jugar': vale_jugar,
    }

    if vale_jugar:
        resultado['accion'] = 'jugar'
        resultado['alternativas'] = palabras[1:4]
    else:
        # Cambiar la ficha con mayor residuo negativo (la que más decepciona)
        ficha_cambiar = min(analisis_fichas, key=lambda d: d['residuo'])
        resultado['accion'] = 'cambiar'
        resultado['ficha_cambiar'] = ficha_cambiar

    return resultado


# ---------------------------------------------------------------------------
# DICCIONARIO  (cargado dinámicamente desde pyspellchecker ~42k palabras)
# ---------------------------------------------------------------------------
_LETRAS_VALIDAS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZÑ')

def _normalizar_palabra(w: str) -> str:
    """Elimina tildes y convierte a mayúsculas, conservando la Ñ."""
    resultado = []
    for c in w.upper():
        if c == 'Ñ':
            resultado.append('Ñ')
            continue
        base = ''.join(
            ch for ch in unicodedata.normalize('NFD', c)
            if unicodedata.category(ch) != 'Mn'
        )
        resultado.append(base)
    return ''.join(resultado)

def _cargar_diccionario() -> list[str]:
    from spellchecker import SpellChecker
    spell = SpellChecker(language='es')
    palabras = set()
    for w in spell.word_frequency.keys():
        if not w.isalpha() or not (2 <= len(w) <= 8):
            continue
        n = _normalizar_palabra(w)
        if all(c in _LETRAS_VALIDAS for c in n):
            palabras.add(n)
    return sorted(palabras)

# Palabras extra de respaldo por si spellchecker no las incluye
_EXTRA = [
    "AMOR", "ARCO", "ARTE", "ARES", "ATAR",
    "BOCA", "BOLA", "BRAZO", "BRISA",
    "CARA", "CARO", "CARTA", "CASA", "CESTA", "CLARO", "COSTA",
    "DEDO", "DELTA", "ECOS", "ETAPA",
    "FARO", "FLOR", "FORMA", "GATO", "GIRO",
    "HIELO", "HOJA", "HORA", "ISLA",
    "LADO", "LAGO", "LARGO", "LETRA", "LIBRO", "LUNA",
    "MALO", "MANO", "MAPA", "MESA", "META",
    "NIDO", "NOCHE", "NUBE", "OBRA", "OLOR", "ORAL", "ORDEN",
    "PALA", "PARA", "PASO", "PATO", "PINO", "POCO", "POLO",
    "RAMA", "RANA", "RATA", "RATON", "REAL", "RIEL",
    "ROCA", "ROJO", "ROSA", "ROTA", "ROTO",
    "SACO", "SALA", "SALTO", "SETA", "SERA", "SOLA", "SOLO", "SOPA",
    "TACO", "TAPA", "TARO", "TASA", "TELA", "TEMA", "TONO",
    "TORO", "TREN", "TRES", "TRIO", "TAREA",
    "VACA", "VELA", "VIDA", "VINO", "VISTA",
    "RATOS", "OSAR", "SOAR", "SOLAR", "LOSA", "LOAS",
    "RATO", "OTRA", "ORAS", "ARTES", "RETAS", "ASTER",
    "RESTA", "TRASTE", "RESTAR",
    "ALTO", "ALBA", "ALMA",
    "FILO", "FINO", "FIRMA",
    "PERRO", "PERRA", "TIERRA", "SIERRA",
    "COMER", "CORRER", "CORTAR", "CERRAR",
    "MEJOR", "MENOR", "MAYOR",
    "LENTO", "LENTA",
    "CORTO", "CORTA",
    "TARDE", "TIGRE",
    "PLATO", "PLATA", "PLAYA",
    "CAMPO", "CANTO",
    "BANCO", "BANDA",
    "MUNDO", "MUJER",
    "PADRE", "MADRE", "PARTE",
    "VERDE", "VUELO", "VALLE",
    "ENTRE", "ENTRA",
    "CALLE", "CALOR", "CALMA",
    "FRUTA", "FUEGO",
    "GRANO",
    "JUEGO", "JUGAR",
    "MIRAR",
    "NOBLE",
    "PAPEL", "PARED",
    "RADIO", "RANGO",
    "SACAR", "SABER",
    "TABLA", "TALAR",
    "VALOR", "VAPOR",
    "ZONA", "ZORRO",
]


def construir_trie() -> Trie:
    """Carga ~42k palabras del diccionario español y las inserta en el Trie."""
    trie = Trie()
    try:
        palabras = _cargar_diccionario()
    except Exception:
        palabras = []
    # Mezclar con las palabras extra de respaldo
    todas = set(palabras) | set(_normalizar_palabra(w) for w in _EXTRA)
    for palabra in todas:
        trie.insertar(palabra)
    return trie


# ---------------------------------------------------------------------------
# PRUEBA EN CONSOLA
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    trie = construir_trie()

    for caso in ["A R T E S", "X Z Q J K W", "S O L A R"]:
        r = recomendar(caso, trie)
        c = r['ajuste_curva']
        print(f"Fichas : {caso}")
        print(f"  Polinomio : p(x) = {c['coeficientes'][0]:.4f} "
              f"+ {c['coeficientes'][1]:.4f}x "
              f"+ {c['coeficientes'][2]:.4f}x²")
        print(f"  R²        : {c['r2']}")
        print(f"  Umbral    : {c['umbral']}")
        print(f"  Acción    : {r['accion']}")
        if r['accion'] == 'jugar':
            print(f"  Palabra   : {r['mejor_palabra']} ({r['mejor_puntaje']} pts)")
        else:
            print(f"  Cambiar   : {r['ficha_cambiar']['ficha']} (residuo {r['ficha_cambiar']['residuo']})")
        print()
