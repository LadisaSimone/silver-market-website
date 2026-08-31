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
    if (sentiment === "bearish") return "#ef4444";
    if (sentiment === "neutral") return "#f59e0b";
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
      // d.reason explains why this driver got its color (see
      // docs/scripts/update_daily.py build_drivers()) — older cached data
      // may not have it yet, so only render the line when present.
      const reasonHtml = d.reason
        ? `<p class="driver-reason">${d.reason}</p>`
        : "";
      li.innerHTML = `
        <div class="driver-item-top">
          <span class="driver-dot ${statusClass(d.status)}"></span>
          <span class="driver-name">${d.label}</span>
          <span class="driver-status ${statusClass(d.status)}">${statusLabel(d.status)}</span>
        </div>
        ${reasonHtml}
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

  function historyFor(data, range) {
    const h = data.history;
    if (!h) return [];
    if (Array.isArray(h)) {
      return range === "1M" ? h : [];
    }
    return h[range] || [];
  }

  const DISCLOSURE_TEXT = {
    comex_futures: "Intraday movement based on COMEX Silver Futures",
    spot_snapshots: "Intraday movement based on live spot price snapshots",
  };

  function fmtPct(val) {
    if (val === null || val === undefined || Number.isNaN(val)) return "—";
    return `${val > 0 ? "+" : ""}${val.toFixed(2)}%`;
  }

  function renderChart(data, range) {
    const ctx = document.getElementById("price-chart");
    const emptyEl = document.getElementById("chart-empty");
    const disclosureEl = document.getElementById("chart-disclosure");
    let labels, values, isPercent;

    if (range === "1D") {
      // "Today" tab — see docs/scripts/update_price.py's _build_intraday_chart()
      // for how this series is built (COMEX SI=F shape, percent-normalized,
      // with a spot-snapshot fallback) and why it's never a raw SI=F price.
      const ic = data.intraday_chart || { source: null, points: [] };
      labels = ic.points.map((p) => p.t);
      values = ic.points.map((p) => p.pct);
      isPercent = true;

      if (ic.points.length < 2) {
        emptyEl.hidden = false;
        disclosureEl.hidden = true;
      } else {
        emptyEl.hidden = true;
        disclosureEl.hidden = false;
        disclosureEl.textContent =
          DISCLOSURE_TEXT[ic.source] || "Intraday movement (source unavailable)";
      }
    } else {
      const series = historyFor(data, range);
      labels = series.map((h) => h.date.slice(5));
      values = series.map((h) => h.close);
      isPercent = false;
      emptyEl.hidden = true;
      disclosureEl.hidden = true;
    }

    const lineColor = "#3b82f6";
    const yTickCallback = isPercent ? (val) => fmtPct(val) : (val) => `$${val}`;
    const tooltipLabelCallback = isPercent
      ? (item) => fmtPct(item.parsed.y)
      : (item) => `$${item.parsed.y.toFixed(2)}`;

    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.options.scales.y.ticks.callback = function (val) {
        return yTickCallback(val);
      };
      chart.options.plugins.tooltip.callbacks.label = tooltipLabelCallback;
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
              if (!chartArea) return "rgba(59,130,246,0.08)";
              const g = context.chart.ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, "rgba(59,130,246,0.25)");
              g.addColorStop(1, "rgba(59,130,246,0.0)");
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
            ticks: { color: "#64748b", font: { size: 10 }, maxTicksLimit: 6 },
          },
          y: {
            grid: { color: "#243247" },
            ticks: {
              color: "#64748b",
              font: { size: 10 },
              callback: function (val) {
                return yTickCallback(val);
              },
            },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#142235",
            borderColor: "#243247",
            borderWidth: 1,
            titleColor: "#f1f5f9",
            bodyColor: "#f1f5f9",
            callbacks: {
              label: tooltipLabelCallback,
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
