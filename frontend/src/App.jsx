import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet.heat";

const API_BASE = import.meta.env.VITE_API_URL || "";

const HEAT_MODES = {
  density: {
    id: "density",
    label: "Densidade Geral",
    hint: "Volume total de comentários",
    gradient: { 0.2: "#67e8f9", 0.5: "#0ea5e9", 0.8: "#0369a1", 1.0: "#0c4a6e" },
  },
  positive: {
    id: "positive",
    label: "Calor Positivo",
    hint: "Peso maior para sentimento favorável",
    gradient: { 0.2: "#bbf7d0", 0.5: "#4ade80", 0.8: "#16a34a", 1.0: "#14532d" },
  },
  negative: {
    id: "negative",
    label: "Calor Negativo",
    hint: "Peso maior para rejeição/crítica",
    gradient: { 0.2: "#fecaca", 0.5: "#f87171", 0.8: "#dc2626", 1.0: "#7f1d1d" },
  },
};

function intensityForMode(point, mode) {
  const base = typeof point.intensity === "number" ? point.intensity : 0.5;
  const score = typeof point.sentiment_score === "number" ? point.sentiment_score : 0;
  const sentiment = point.sentiment || "neutro";

  if (mode === "positive") {
    if (sentiment === "negativo") return 0.05;
    if (sentiment === "neutro") return 0.15;
    return Math.max(0.35, base * 0.5 + Math.max(0, score) * 0.7);
  }
  if (mode === "negative") {
    if (sentiment === "positivo") return 0.05;
    if (sentiment === "neutro") return 0.15;
    return Math.max(0.35, base * 0.5 + Math.max(0, -score) * 0.7);
  }
  return Math.max(0.25, base);
}

function HeatMap({ points, mode }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const heatRef = useRef(null);
  const markersRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [-14.235, -51.9253],
      zoom: 4,
      minZoom: 3,
      maxZoom: 12,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      heatRef.current = null;
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const heatData = points.map((p) => [
      p.lat,
      p.lng,
      intensityForMode(p, mode),
    ]);

    if (heatRef.current) {
      map.removeLayer(heatRef.current);
      heatRef.current = null;
    }

    heatRef.current = L.heatLayer(heatData, {
      radius: 32,
      blur: 22,
      maxZoom: 10,
      max: 1.0,
      minOpacity: 0.35,
      gradient: HEAT_MODES[mode].gradient,
    }).addTo(map);

    if (markersRef.current) {
      markersRef.current.clearLayers();
      points.forEach((p) => {
        const color =
          p.sentiment === "positivo"
            ? "#15803d"
            : p.sentiment === "negativo"
              ? "#b91c1c"
              : "#64748b";
        const marker = L.circleMarker([p.lat, p.lng], {
          radius: 5,
          color,
          weight: 1.5,
          fillColor: color,
          fillOpacity: 0.55,
        });
        marker.bindPopup(
          `<div style="max-width:240px;font-size:13px;line-height:1.4">
            <strong>${p.location || "Brasil"}</strong>
            <span style="color:${color}"> · ${p.sentiment}</span>
            <p style="margin:6px 0 0">${escapeHtml(p.text || "")}</p>
          </div>`
        );
        markersRef.current.addLayer(marker);
      });
    }
  }, [points, mode]);

  return <div ref={containerRef} className="h-full w-full" />;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export default function App() {
  const [query, setQuery] = useState("Pablo Marçal");
  const [mode, setMode] = useState("density");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [payload, setPayload] = useState(null);

  const fetchHeatmap = useCallback(async (term) => {
    const q = term.trim();
    if (!q) {
      setError("Informe uma palavra-chave.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const url = `${API_BASE}/api/heatmap-data?query=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Erro HTTP ${res.status}`);
      }
      const data = await res.json();
      setPayload(data);
    } catch (err) {
      setError(err.message || "Falha ao carregar dados do mapa.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHeatmap(query);
    // carga inicial apenas
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const points = useMemo(() => payload?.points || [], [payload]);
  const summary = payload?.summary || { positivo: 0, neutro: 0, negativo: 0 };

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-5 px-4 py-6 md:px-6">
      <header className="fade-in flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="font-display text-3xl font-semibold tracking-tight text-ocean md:text-4xl">
            MapadeCalor
          </p>
          <h1 className="mt-2 text-lg font-medium tracking-tight text-ink md:text-xl">
            Sentimentos no mapa
          </h1>
          <p className="mt-1 max-w-xl text-sm text-slate-600">
            Comentários públicos do YouTube analisados por sentimento e projetados
            em um mapa de calor geográfico do Brasil.
          </p>
        </div>
        {payload && (
          <div className="rounded-xl bg-white/70 px-4 py-2 text-xs text-slate-600 shadow-sm ring-1 ring-slate-200/80 backdrop-blur">
            Fonte: <span className="font-medium text-ink">{payload.source}</span>
            {" · "}
            {payload.total} pontos
          </div>
        )}
      </header>

      <section className="fade-in rounded-2xl bg-white/80 p-4 shadow-sm ring-1 ring-slate-200/80 backdrop-blur md:p-5">
        <form
          className="flex flex-col gap-3 md:flex-row md:items-center"
          onSubmit={(e) => {
            e.preventDefault();
            fetchHeatmap(query);
          }}
        >
          <label className="sr-only" htmlFor="query">
            Palavra-chave
          </label>
          <input
            id="query"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='Ex: "Pablo Marçal"'
            className="w-full flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none ring-ocean/30 transition focus:ring-2"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-ocean px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <>
                <span className="loading-dot inline-block h-1.5 w-1.5 rounded-full bg-white" />
                <span className="loading-dot inline-block h-1.5 w-1.5 rounded-full bg-white" />
                <span className="loading-dot inline-block h-1.5 w-1.5 rounded-full bg-white" />
                <span>Atualizando…</span>
              </>
            ) : (
              "Atualizar Mapa"
            )}
          </button>
        </form>

        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Modo de calor">
            {Object.values(HEAT_MODES).map((item) => {
              const active = mode === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setMode(item.id)}
                  title={item.hint}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "bg-ink text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap gap-3 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-moss" /> Positivo {summary.positivo}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-slate-400" /> Neutro {summary.neutro}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-ember" /> Negativo {summary.negativo}
            </span>
          </div>
        </div>

        {error && (
          <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 ring-1 ring-red-100">
            {error}
          </p>
        )}
      </section>

      <section className="fade-in map-shell overflow-hidden rounded-2xl shadow-md ring-1 ring-slate-200/80">
        <HeatMap points={points} mode={mode} />
        {loading && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-slate-900/20 backdrop-blur-[1px]">
            <div className="rounded-xl bg-white/95 px-4 py-3 text-sm font-medium text-ink shadow-lg">
              Coletando e analisando comentários…
            </div>
          </div>
        )}
      </section>

      <footer className="pb-4 text-center text-xs text-slate-500">
        MVP · YouTube Data API · NLP de sentimento · Leaflet Heat · OpenStreetMap
      </footer>
    </div>
  );
}
