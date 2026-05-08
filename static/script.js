const PUNTAJES = {
  A:1,E:1,I:1,O:1,U:1,L:1,N:1,R:1,S:1,T:1,
  D:2,G:2,B:3,C:3,M:3,P:3,F:4,H:4,V:4,Y:4,
  Q:5,J:8,X:8,'Ñ':8,Z:10,K:10,W:10,
};

let graficaInstancia = null;

// ── Teclado rápido ──────────────────────────────────────────────────────────
(function buildTeclado() {
  const container = document.getElementById('teclas');
  Object.entries(PUNTAJES)
    .sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]))
    .forEach(([letra, pts]) => {
      const btn = document.createElement('button');
      btn.className = 'tecla';
      btn.innerHTML = `${letra}<span class="pts">${pts}pt</span>`;
      btn.onclick = () => insertarLetra(letra);
      container.appendChild(btn);
    });
})();

function insertarLetra(letra) {
  const input = document.getElementById('fichas-input');
  const val = input.value.trim();
  input.value = val ? val + ' ' + letra : letra;
  input.focus();
}

document.getElementById('fichas-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') analizar();
});

// ── Llamada al backend ───────────────────────────────────────────────────────
async function analizar() {
  const fichas = document.getElementById('fichas-input').value.trim();
  if (!fichas) return;
  setEstado('loading');
  try {
    const res = await fetch('/analizar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fichas }),
    });
    const data = await res.json();
    if (!res.ok) { setEstado('error', data.error); return; }
    renderResultado(data);
    setEstado('resultado');
  } catch {
    setEstado('error', 'Error de conexión. Intenta de nuevo.');
  }
}

// ── Render ───────────────────────────────────────────────────────────────────
function renderResultado(d) {
  const c = d.ajuste_curva;

  // Badge decisión
  const badge = document.getElementById('accion-badge');
  if (d.accion === 'jugar') {
    badge.textContent = `✓ JUEGA: ${d.mejor_palabra}  (${d.mejor_puntaje} pts)`;
    badge.className = 'badge-jugar';
  } else {
    badge.textContent = `✗ CAMBIA: ${d.ficha_cambiar.ficha}  (residuo ${d.ficha_cambiar.residuo})`;
    badge.className = 'badge-cambiar';
  }

  // Fichas con ficha resaltada
  const fichaResaltada = d.accion === 'cambiar' ? d.ficha_cambiar.ficha : null;
  const display = document.getElementById('fichas-display');
  display.innerHTML = '';
  d.fichas.forEach(f => {
    const tile = document.createElement('div');
    tile.className = 'ficha-tile' + (f === fichaResaltada ? ' resaltada' : '');
    tile.innerHTML = `${f}<span class="ficha-pts">${PUNTAJES[f] ?? 0}</span>`;
    display.appendChild(tile);
  });

  // Palabras (Trie)
  document.getElementById('total-palabras').textContent =
    `${d.total_palabras} palabra(s) · umbral estratégico: ${c.umbral} pts`;
  const lista = document.getElementById('palabras-lista');
  lista.innerHTML = '';
  if (!d.palabras.length) {
    lista.innerHTML = '<li style="color:var(--muted)">Ninguna palabra válida.</li>';
  } else {
    d.palabras.forEach((p, i) => {
      const score = [...p].reduce((s, ch) => s + (PUNTAJES[ch] ?? 0), 0);
      const li = document.createElement('li');
      if (i === 0) li.className = 'mejor';
      li.innerHTML = `<span>${i === 0 ? '⭐ ' : ''}${p}</span><span class="pts-word">${score} pts</span>`;
      lista.appendChild(li);
    });
  }

  // Métricas del ajuste
  const [c0, c1, c2] = c.coeficientes;
  document.getElementById('curva-metricas').innerHTML =
    metrica(c.r2, 'R²') +
    metrica(c.iteraciones_gauss ?? '3×3', 'Sistema Gauss') +
    metrica(c.umbral, 'Umbral');

  // Ecuación del polinomio
  document.getElementById('ecuacion').textContent =
    `p(x) = ${c0.toFixed(4)} + (${c1.toFixed(4)})·x + (${c2.toFixed(4)})·x²`;

  // Gráfica
  renderGrafica(c, d.analisis_fichas, d.accion === 'cambiar' ? d.ficha_cambiar.ficha : null);

  // Tabla de fichas
  const tbody = document.getElementById('fichas-tbody');
  tbody.innerHTML = '';
  d.analisis_fichas.forEach(f => {
    const esCambiar = d.accion === 'cambiar' && f.ficha === d.ficha_cambiar?.ficha;
    const tr = document.createElement('tr');
    if (esCambiar) tr.className = 'fila-cambiar';
    tr.innerHTML = `
      <td>${f.ficha}${esCambiar ? ' ⬅' : ''}</td>
      <td>${f.frecuencia}</td>
      <td>${f.puntaje_real}</td>
      <td>${f.valor_estimado}</td>
      <td class="${f.residuo < 0 ? 'residuo-neg' : 'residuo-pos'}">${f.residuo > 0 ? '+' : ''}${f.residuo}</td>
    `;
    tbody.appendChild(tr);
  });

  // Detalle ecuaciones normales (Gauss)
  const gaussDiv = document.getElementById('gauss-detalle');
  gaussDiv.innerHTML = '';
  c.pasos_gauss.forEach(paso => {
    const bloque = document.createElement('div');
    bloque.style.marginBottom = '.75rem';
    if (Array.isArray(paso.valor[0])) {
      // Matriz
      const filas = paso.valor.map(fila => '  [ ' + fila.map(v => String(v).padStart(12)).join('  ') + ' ]').join('\n');
      bloque.textContent = `${paso.nombre}:\n${filas}`;
    } else {
      // Vector
      bloque.textContent = `${paso.nombre}:\n  [ ${paso.valor.join(',  ')} ]`;
    }
    gaussDiv.appendChild(bloque);
  });
}

// ── Gráfica Chart.js ─────────────────────────────────────────────────────────
function renderGrafica(c, analisisFichas, fichaResaltada) {
  if (graficaInstancia) { graficaInstancia.destroy(); graficaInstancia = null; }

  const ctx = document.getElementById('curvaChart').getContext('2d');

  // Nube de puntos: todas las letras del español
  const puntosEspanol = c.puntos_datos.map(p => ({ x: p.x, y: p.y, label: p.letra }));

  // Fichas actuales del usuario
  const puntosFichas = analisisFichas.map(f => ({
    x: f.frecuencia,
    y: f.puntaje_real,
    label: f.ficha,
    resaltada: f.ficha === fichaResaltada,
  }));

  // Curva ajustada
  const curvaDatos = c.puntos_curva.map(p => ({ x: p.x, y: p.y }));

  graficaInstancia = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Curva ajustada p(x)',
          data: curvaDatos,
          type: 'line',
          borderColor: '#6366f1',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.4,
          order: 1,
        },
        {
          label: 'Letras del español',
          data: puntosEspanol,
          backgroundColor: 'rgba(148,163,184,0.5)',
          pointRadius: 4,
          order: 2,
        },
        {
          label: 'Tus fichas',
          data: puntosFichas,
          backgroundColor: puntosFichas.map(p =>
            p.resaltada ? '#ef4444' : '#22d3ee'
          ),
          pointRadius: 7,
          pointStyle: 'rectRot',
          order: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const raw = ctx.raw;
              return raw.label
                ? `${raw.label}: freq=${raw.x}%, pts=${raw.y}`
                : `(${raw.x.toFixed(2)}, ${raw.y.toFixed(2)})`;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: 'Frecuencia en español (%)', color: '#94a3b8' },
          ticks: { color: '#94a3b8' },
          grid:  { color: '#1e293b' },
        },
        y: {
          title: { display: true, text: 'Puntaje Scrabble', color: '#94a3b8' },
          ticks: { color: '#94a3b8' },
          grid:  { color: '#1e293b' },
        },
      },
    },
  });
}

function metrica(val, lbl) {
  return `<div class="metrica"><div class="val">${val}</div><div class="lbl">${lbl}</div></div>`;
}

// ── Estado UI ────────────────────────────────────────────────────────────────
function setEstado(estado, msg = '') {
  ['loader', 'resultado', 'error-box'].forEach(id =>
    document.getElementById(id).classList.add('hidden')
  );
  if (estado === 'loading')   document.getElementById('loader').classList.remove('hidden');
  if (estado === 'resultado') document.getElementById('resultado').classList.remove('hidden');
  if (estado === 'error') {
    document.getElementById('error-msg').textContent = '⚠ ' + msg;
    document.getElementById('error-box').classList.remove('hidden');
  }
}
