/**
 * Cookie consent banner + gated Google Analytics loader.
 *
 * This site sets no cookies of its own. Google Analytics (once accepted)
 * does — so GA is never loaded until a visitor explicitly accepts. There's
 * no backend here (GitHub Pages, static hosting only) to geo-detect EU/UK/
 * Swiss visitors, so rather than guess, this banner is shown to every
 * visitor on their first visit — the simplest way to stay correct
 * everywhere without adding any server-side infrastructure.
 *
 * Included on every page that should carry analytics (docs/index.html,
 * via docs/index.template.html, and docs/privacy.html). Loaded with
 * `defer` so it never blocks page rendering.
 */
(function () {
  "use strict";

  // GA4 property: Silver Market Intelligence (analytics.google.com).
  var GA_MEASUREMENT_ID = "G-V6PW3YCWNY";

  var CONSENT_KEY = "smi_analytics_consent"; // "granted" | "denied"

  function loadGA() {
    if (!GA_MEASUREMENT_ID || GA_MEASUREMENT_ID.indexOf("XXXX") !== -1) {
      return;
    }
    var script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    function gtag() {
      window.dataLayer.push(arguments);
    }
    window.gtag = gtag;
    gtag("js", new Date());
    // anonymize_ip: strips the last IP octet before Google stores it —
    // reduces (does not eliminate) how identifying the stored data is.
    gtag("config", GA_MEASUREMENT_ID, { anonymize_ip: true });
  }

  function getStoredConsent() {
    try {
      return window.localStorage.getItem(CONSENT_KEY);
    } catch (e) {
      // Private browsing / storage blocked — treat as "no stored
      // choice" rather than crash; the banner will just show again.
      return null;
    }
  }

  function storeConsent(value) {
    try {
      window.localStorage.setItem(CONSENT_KEY, value);
    } catch (e) {
      // Nothing we can do — the choice just won't persist across visits.
    }
  }

  function showBanner() {
    var banner = document.createElement("div");
    banner.className = "consent-banner";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-label", "Cookie consent");
    banner.innerHTML =
      '<p class="consent-text">This site uses Google Analytics to understand traffic. ' +
      "No analytics cookies are set unless you accept. See our " +
      '<a href="privacy.html">Privacy Policy</a>.</p>' +
      '<div class="consent-actions">' +
      '<button type="button" class="consent-btn consent-decline">Decline</button>' +
      '<button type="button" class="consent-btn consent-accept">Accept</button>' +
      "</div>";
    document.body.appendChild(banner);

    banner.querySelector(".consent-accept").addEventListener("click", function () {
      storeConsent("granted");
      banner.remove();
      loadGA();
    });
    banner.querySelector(".consent-decline").addEventListener("click", function () {
      storeConsent("denied");
      banner.remove();
    });
  }

  var consent = getStoredConsent();
  if (consent === "granted") {
    loadGA();
  } else if (consent !== "denied") {
    showBanner();
  }
  // consent === "denied": do nothing — no banner, no GA.
})();
