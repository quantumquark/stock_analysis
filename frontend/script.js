/* ============================================================
   script.js — S&P 500 Stock Analysis Frontend
   ============================================================ */

const API_BASE = "http://localhost:5000/api";

let choicesInstance = null;
let priceChart = null;
let currentTicker = null;
let currentPeriod = "1y";
let debounceTimer = null;

// ── Init ─────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  initChoices();
  initPeriodButtons();
  loadDbStats();
});

// ── Choices.js (autocomplete) ────────────────────────────────

function initChoices() {
  const selectEl = document.getElementById("stock-select");

  choicesInstance = new Choices(selectEl, {
    searchEnabled: true,
    searchPlaceholderValue: "Type ticker or company name…",
    itemSelectText: "",
    noResultsText: "No matching stocks found",
    noChoicesText: "Start typing to search…",
    shouldSort: false,
    searchResultLimit: 20,
    fuseOptions: { threshold: 0.4 },
  });

  // Disable built-in search; we use our own server-side search
  selectEl.addEventListener("search", (e) => {
    const q = e.detail.value.trim();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fetchSearchResults(q), 250);
  });

  selectEl.addEventListener("change", (e) => {
    const ticker = e.detail.value;
    if (ticker) {
      currentTicker = ticker;
      currentPeriod = "1y";
      setActivePeriodBtn("1y");
      loadStock(ticker);
    }
  });
}

async function fetchSearchResults(query) {
  if (!query || query.length < 1) return;
  try {
    const res = await fetch(`${API_BASE}/stocks/search?q=${encodeURIComponent(query)}`);
    const stocks = await res.json();

    const choices = stocks.map((s) => ({
      value: s.ticker,
      label: `${s.ticker} — ${s.name}`,
      customProperties: { ticker: s.ticker, name: s.name, sector: s.sector },
    }));

    choicesInstance.clearChoices();
    choicesInstance.setChoices(choices, "value", "label", true);
  } catch (err) {
    console.error("Search error:", err);
  }
}

// ── Example chips ────────────────────────────────────────────

async function pickExample(query) {
  const res = await fetch(`${API_BASE}/stocks/search?q=${encodeURIComponent(query)}`);
  const stocks = await res.json();
  if (!stocks.length) return;

  const s = stocks[0];
  choicesInstance.clearChoices();
  choicesInstance.setChoices(
    [{ value: s.ticker, label: `${s.ticker} — ${s.name}`, selected: true }],
    "value",
    "label",
    true
  );
  currentTicker = s.ticker;
  currentPeriod = "1y";
  setActivePeriodBtn("1y");
  loadStock(s.ticker);
}

// ── Period buttons ───────────────────────────────────────────

function initPeriodButtons() {
  document.querySelectorAll(".btn-period").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!currentTicker) return;
      currentPeriod = btn.dataset.period;
      setActivePeriodBtn(currentPeriod);
      loadPrices(currentTicker, currentPeriod);
    });
  });
}

function setActivePeriodBtn(period) {
  document.querySelectorAll(".btn-period").forEach((b) => {
    b.classList.toggle("active", b.dataset.period === period);
  });
}

// ── Load stock (metadata + prices) ──────────────────────────

async function loadStock(ticker) {
  showLoading(true);
  try {
    const [meta, prices] = await Promise.all([
      fetchMeta(ticker),
      fetchPrices(ticker, currentPeriod),
    ]);
    renderBanner(meta);
    renderChart(ticker, prices);
  } catch (err) {
    showError(err.message || "Failed to load stock data.");
  } finally {
    showLoading(false);
  }
}

async function loadPrices(ticker, period) {
  showLoading(true);
  try {
    const prices = await fetchPrices(ticker, period);
    renderChart(ticker, prices);
  } catch (err) {
    showError(err.message || "Failed to load price data.");
  } finally {
    showLoading(false);
  }
}

// ── API calls ────────────────────────────────────────────────

async function fetchMeta(ticker) {
  const res = await fetch(`${API_BASE}/stocks/${ticker}`);
  if (!res.ok) throw new Error(`Stock '${ticker}' not found in database.`);
  return res.json();
}

async function fetchPrices(ticker, period) {
  const res = await fetch(`${API_BASE}/stocks/${ticker}/prices?period=${period}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.error || "No price data found.");
  }
  return res.json();
}

async function loadDbStats() {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    const data = await res.json();
    const el = document.getElementById("db-stats");
    if (data.stocks) {
      el.textContent = `${data.stocks} stocks · ${data.price_rows.toLocaleString()} price rows · last updated ${data.latest_date}`;
    }
  } catch (_) {
    // silent
  }
}

// ── Render banner ────────────────────────────────────────────

function renderBanner(meta) {
  document.getElementById("banner-ticker").textContent = meta.ticker;
  document.getElementById("banner-name").textContent = meta.name;
  document.getElementById("banner-sector").textContent = meta.sector || "N/A";
  document.getElementById("banner-industry").textContent = meta.industry || "";

  document.getElementById("stock-banner").classList.remove("d-none");
  document.getElementById("chart-card").classList.remove("d-none");
  document.getElementById("empty-state").classList.add("d-none");
}

// ── Render chart ─────────────────────────────────────────────

function renderChart(ticker, prices) {
  const labels = prices.map((p) => p.date);
  const closes = prices.map((p) => p.close);
  const volumes = prices.map((p) => p.volume);

  // Summary stats
  const latestClose = closes[closes.length - 1];
  const firstClose = closes[0];
  const periodHigh = Math.max(...closes);
  const periodLow = Math.min(...closes);
  const periodReturn = ((latestClose - firstClose) / firstClose) * 100;

  document.getElementById("stat-close").textContent = fmt(latestClose);
  document.getElementById("stat-high").textContent = fmt(periodHigh);
  document.getElementById("stat-low").textContent = fmt(periodLow);
  const retEl = document.getElementById("stat-return");
  retEl.textContent = `${periodReturn >= 0 ? "+" : ""}${periodReturn.toFixed(2)}%`;
  retEl.className = `stat-value ${periodReturn >= 0 ? "text-success" : "text-danger"}`;
  document.getElementById("stats-row").classList.remove("d-none");

  // Chart title
  document.getElementById("chart-title").textContent = `${ticker} — Closing Price`;

  // Destroy existing chart
  if (priceChart) {
    priceChart.destroy();
    priceChart = null;
  }

  // Color based on performance
  const lineColor = periodReturn >= 0 ? "#22c55e" : "#ef4444";
  const fillColor = periodReturn >= 0 ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)";

  const ctx = document.getElementById("priceChart").getContext("2d");
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Close",
          data: closes,
          borderColor: lineColor,
          backgroundColor: fillColor,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.1,
          yAxisID: "yPrice",
        },
        {
          label: "Volume",
          data: volumes,
          borderColor: "rgba(100,116,139,0.3)",
          backgroundColor: "rgba(100,116,139,0.15)",
          borderWidth: 1,
          pointRadius: 0,
          fill: true,
          type: "bar",
          yAxisID: "yVolume",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            title: (ctx) => ctx[0].label,
            label: (ctx) => {
              if (ctx.dataset.label === "Close") {
                return ` Close: ${fmt(ctx.parsed.y)}`;
              }
              if (ctx.dataset.label === "Volume") {
                return ` Volume: ${fmtVol(ctx.parsed.y)}`;
              }
              return ctx.formattedValue;
            },
          },
          backgroundColor: "#1e293b",
          titleColor: "#94a3b8",
          bodyColor: "#f8fafc",
          borderColor: "#334155",
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
        },
        zoom: {
          pan: { enabled: true, mode: "x" },
          zoom: {
            wheel: { enabled: true },
            pinch: { enabled: true },
            mode: "x",
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10,
            color: "#94a3b8",
            maxRotation: 0,
          },
          grid: { color: "#f1f5f9" },
        },
        yPrice: {
          position: "left",
          ticks: {
            color: "#64748b",
            callback: (v) => fmt(v),
          },
          grid: { color: "#f1f5f9" },
        },
        yVolume: {
          position: "right",
          ticks: {
            color: "#94a3b8",
            callback: (v) => fmtVol(v),
            maxTicksLimit: 4,
          },
          grid: { display: false },
        },
      },
    },
  });

  // Show chart container
  document.getElementById("chart-container").style.display = "";
  hideError();
}

// ── Helpers ──────────────────────────────────────────────────

function fmt(n) {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtVol(n) {
  if (n == null) return "—";
  if (n >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return n.toString();
}

function showLoading(show) {
  document.getElementById("chart-loading").classList.toggle("d-none", !show);
  document.getElementById("chart-container").style.display = show ? "none" : "";
}

function showError(msg) {
  const el = document.getElementById("chart-error");
  el.textContent = msg;
  el.classList.remove("d-none");
  document.getElementById("chart-container").style.display = "none";
}

function hideError() {
  document.getElementById("chart-error").classList.add("d-none");
}
