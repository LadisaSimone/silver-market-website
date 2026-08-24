(function () {
  "use strict";

  const RING_CIRCUMFERENCE = 2 * Math.PI * 60; // r=60, matches styles.css

  function fmtSigned(n, opts) {
    if (n === null || n === undefined || Number.isNaN(n)) return "—";
    const sign = n > 0 ? "+" : "";
    return sign + n.toFixed(opts && opts.decimals !== undefined ? opts.decimals : 2);
  }

  function sentimentClass(sentiment) {
    if (sentiment === "bearish") return "is-bearish";
    if (sentiment === "neutral") return "is-neutral";
    return ""; // bullish is the default styling
  }

  function sentimentColor(sentiment) {
    if (sentiment === "bearish") return "#ff4d5e";
    if (sentiment === "neutral") return "#f5a623";
    return "#22c55e";
  }

  function statusClass(status) {
    if (status === "risk") return "is-risk";
    if (status === "neutral") return "is-neutral";
    return "is-supportive";
  }

  function statusLabel(status) {
    if (status === "risk") return "Risk";
    if (status === "neutral") return "Neutral";
    return "Supportive";
  }

  function relativeUpdated(iso) {
    if (!iso) return "";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "";
    const diffMin = Math.round((Date.now() - then) / 60000);
    if (diffMin < 1) return "Updated just now";
    if (diffMin < 60) return `Updated ${diffMin}m ago`;
    const diffH = Math.round(diffMin / 60);
    if (diffH < 24) return `Updated ${diffH}h ago`;
    const diffD = Math.round(diffH / 24);
    return `Updated ${diffD}d ago`;
  }

  function renderPrice(data) {
    const p = data.price || {};
    document.getElementById("price-value").textContent =
      p.value !== undefined && p.value !== null ? `$${p.value.toFixed(2)}` : "—";

    const changeEl = document.getElementById("price-change");
    const up = (p.change || 0) >= 0;
    changeEl.textContent =
      p.change !== undefined && p.change !== null
        ? `${fmtSigned(p.change)} (${fmtSigned(p.change_pct)}%)`
        : "—";
    changeEl.className = "price-change " + (up ? "is-up" : "is-down");

    document.getElementById("price-asof").textContent = p.as_of
      ? `As of ${p.as_of}`
      : relativeUpdated(data.updated_at);
  }

  function renderOutlook(data) {
    const o = data.outlook || {};
    const score = typeof o.score === "number" ? o.score : 0;

    const fillEl = document.getElementById("score-ring-fill");
    const offset = RING_CIRCUMFERENCE * (1 - Math.max(0, Math.min(10, score)) / 10);
    fillEl.style.stroke = sentimentColor(o.sentiment);
    // Force a reflow so the transition animates from full offset.
    requestAnimationFrame(() => {
      fillEl.style.strokeDashoffset = String(offset);
    });

    document.getElementById("score-number").textContent =
      typeof o.score === "number" ? o.score : "—";

    const labelEl = document.getElementById("outlook-label");
    labelEl.textContent = o.label || "—";
    labelEl.className = "outlook-label " + sentimentClass(o.sentiment);

    document.getElementById("outlook-summary").textContent =
      o.summary || "No briefing available yet.";
    document.getElementById("outlook-updated").textContent =
      o.updated_at || relativeUpdated(data.updated_at);
  }

  function renderDrivers(data) {
    const list = document.getElementById("driver-list");
    list.innerHTML = "";
    (data.drivers || []).forEach((d) => {
      const li = document.createElement("li");
      li.className = "driver-item";
      li.innerHTML = `
        <span class="driver-dot ${statusClass(d.status)}"></span>
        <span class="driver-name">${d.label}</span>
        <span class="driver-status ${statusClass(d.status)}">${statusLabel(d.status)}</span>
      `;
      list.appendChild(li);
    });
  }

  function renderMetrics(data) {
    const grid = document.getElementById("metrics-grid");
    grid.innerHTML = "";
    (data.metrics || []).forEach((m) => {
      const cell = document.createElement("div");
      cell.className = "metric-cell";
      const hasChange = m.change && String(m.change).trim().length > 0;
      cell.innerHTML = `
        <span class="metric-label">${m.label}</span>
        <span class="metric-value">${m.value}${
          hasChange
            ? `<span class="metric-change ${m.direction === "down" ? "is-down" : "is-up"}">${m.change}</span>`
            : ""
        }</span>
        ${m.note ? `<span class="metric-note">${m.note}</span>` : ""}
      `;
      grid.appendChild(cell);
    });
  }

  function renderStories(data) {
    const list = document.getElementById("story-list");
    list.innerHTML = "";
    (data.stories || []).forEach((s) => {
      const li = document.createElement("li");
      li.className = "story-item";
      const isLink = s.url && s.url !== "#";
      li.innerHTML = `
        <a class="story-link" href="${s.url || "#"}" ${isLink ? 'target="_blank" rel="noopener"' : 'tabindex="-1" style="pointer-events:none"'}>
          <p class="story-title">${s.title}</p>
          <p class="story-summary">${s.summary || ""}</p>
          <span class="story-time">${s.time_ago || ""}</span>
        </a>
      `;
      list.appendChild(li);
    });
  }

  let chart = null;

  function renderChart(data, range) {
    const ctx = document.getElementById("price-chart");
    let labels, values;

    if (range === "1M") {
      labels = (data.history || []).map((h) => h.date.slice(5));
      values = (data.history || []).map((h) => h.close);
    } else {
      labels = (data.intraday || []).map((i) => i.t);
      values = (data.intraday || []).map((i) => i.p);
    }

    const lineColor = "#22c55e";

    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.update();
      return;
    }

    chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            data: values,
            borderColor: lineColor,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            tension: 0.3,
            fill: true,
            backgroundColor: (context) => {
              const chartArea = context.chart.chartArea;
              if (!chartArea) return "rgba(34,197,94,0.08)";
              const g = context.chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, "rgba(34,197,94,0.25)");
              g.addColorStop(1, "rgba(34,197,94,0.0)");
              return g;
            },
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#6b7871", font: { size: 10 }, maxTicksLimit: 6 },
          },
          y: {
            grid: { color: "#1d3327" },
            ticks: { color: "#6b7871", font: { size: 10 } },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0f1613",
            borderColor: "#1d3327",
            borderWidth: 1,
            titleColor: "#f4f6f5",
            bodyColor: "#f4f6f5",
            callbacks: {
              label: (item) => `$${item.parsed.y.toFixed(2)}`,
            },
          },
        },
      },
    });
  }

  function wireChartTabs(data) {
    const tabs = document.querySelectorAll(".chart-tab");
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => {
          t.classList.remove("is-active");
          t.setAttribute("aria-selected", "false");
        });
        tab.classList.add("is-active");
        tab.setAttribute("aria-selected", "true");
        renderChart(data, tab.dataset.range);
      });
    });
  }

  function safe(fn, label) {
    try {
      fn();
    } catch (err) {
      console.error(`Render step failed (${label}):`, err);
    }
  }

  function render(data) {
    safe(() => renderPrice(data), "price");
    safe(() => renderOutlook(data), "outlook");
    safe(() => renderDrivers(data), "drivers");
    safe(() => renderMetrics(data), "metrics");
    safe(() => renderStories(data), "stories");
    safe(() => {
      if (typeof Chart === "undefined") {
        throw new Error("Chart.js failed to load");
      }
      renderChart(data, "1D");
      wireChartTabs(data);
    }, "chart");
  }

  function renderError() {
    document.getElementById("outlook-summary").textContent =
      "Live data is temporarily unavailable. Please check back shortly.";
  }

  fetch("data.json", { cache: "no-store" })
    .then((res) => {
      if (!res.ok) throw new Error("data.json fetch failed: " + res.status);
      return res.json();
    })
    .then(render)
    .catch((err) => {
      console.error(err);
      renderError();
    });
})();
