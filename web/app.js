(() => {
  "use strict";

  // Todos los registros de la vista interactiva son ficticios.
  const views = {
    resumen: {
      title: "Todo bajo control.",
      subtitle: "Una vista clara de los comprobantes de tu cliente.",
      stats: [["Comprobantes", "128", " CFDI", "En este periodo"], ["Ingresos", "$248,500", ".00", "Emitidos"], ["Egresos", "$86,240", ".00", "Recibidos"]],
      tableTitle: "Comprobantes recientes",
      headers: ["Comprobante", "Tipo", "Estado SAT", "Importe"],
      rows: [["Factura A-1042", "08 ene 2026", "Ingreso", "Vigente", "$18,560.00"], ["Factura A-1041", "07 ene 2026", "Ingreso", "Vigente", "$12,180.00"], ["Factura B-0286", "06 ene 2026", "Egreso", "Sin consultar", "$4,350.00"]]
    },
    cfdi: {
      title: "Cada CFDI, en su lugar.",
      subtitle: "Revisa tus XML por tipo, RFC, serie o folio.",
      stats: [["Emitidos", "80", " CFDI", "En este periodo"], ["Recibidos", "48", " CFDI", "En este periodo"], ["Formatos", "4.0", " CFDI", "Información estructurada"]],
      tableTitle: "Administración de XML",
      headers: ["Comprobante", "Tipo", "Estado SAT", "Importe"],
      rows: [["Factura A-1042", "RFC: XAXX010101000", "Ingreso", "Vigente", "$18,560.00"], ["Nota de crédito NC-018", "RFC: XAXX010101000", "Egreso", "Vigente", "$1,160.00"], ["Factura A-1038", "RFC: XAXX010101000", "Ingreso", "Cancelado", "$5,800.00"]]
    },
    pagos: {
      title: "Conecta cada pago.",
      subtitle: "Relaciona tus facturas PPD con sus complementos REP.",
      stats: [["Complementos", "12", " REP", "Pagos registrados"], ["Importe pagado", "$72,500", ".00", "En este periodo"], ["Saldo insoluto", "$18,560", ".00", "En documentos relacionados"]],
      tableTitle: "Conciliación de pagos",
      headers: ["Complemento", "Factura", "Situación", "Pagado"],
      rows: [["Pago P-0084", "08 ene 2026", "A-1040", "Liquidada", "$23,200.00"], ["Pago P-0083", "07 ene 2026", "A-1039", "Pago parcial", "$9,280.00"], ["Pago P-0082", "06 ene 2026", "A-1037", "Liquidada", "$17,400.00"]]
    },
    nomina: {
      title: "Nómina, con claridad.",
      subtitle: "Revisa los datos de tus recibos y expórtalos a Excel.",
      stats: [["Recibos", "24", " CFDI", "En este periodo"], ["Percepciones", "$156,000", ".00", "Total de ejemplo"], ["Deducciones", "$18,720", ".00", "Total de ejemplo"]],
      tableTitle: "Recibos de nómina",
      headers: ["Recibo", "Periodo", "Estado SAT", "Neto"],
      rows: [["Nómina N-0024", "Empleado de ejemplo 03", "Quincenal", "Vigente", "$5,720.00"], ["Nómina N-0023", "Empleado de ejemplo 02", "Quincenal", "Vigente", "$5,720.00"], ["Nómina N-0022", "Empleado de ejemplo 01", "Quincenal", "Vigente", "$5,720.00"]]
    },
    boveda: {
      title: "Un lugar para tus XML.",
      subtitle: "Organiza los archivos por cliente, dirección y periodo.",
      stats: [["Emitidos", "80", " XML", "Enero 2026"], ["Recibidos", "48", " XML", "Enero 2026"], ["Duplicados", "0", " nuevos", "Identificación por UUID"]],
      tableTitle: "Bóveda de XML",
      headers: ["Carpeta", "Dirección", "Periodo", "Archivos"],
      rows: [["Enero", "Comercial del Centro", "Emitidos", "2026", "80 XML"], ["Enero", "Comercial del Centro", "Recibidos", "2026", "48 XML"], ["Febrero", "Comercial del Centro", "Recibidos", "2026", "36 XML"]]
    }
  };

  const tabs = Array.from(document.querySelectorAll(".demo-tab"));
  const panel = document.querySelector("#demo-panel");
  const icon = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const pillClass = (value) => ["Vigente", "Liquidada"].includes(value) ? "pill-green" : value === "Pago parcial" ? "pill-blue" : "pill-neutral";

  function selectView(tab) {
    const key = tab.dataset.view;
    const view = views[key];
    if (!view) return;
    tabs.forEach((item) => {
      const active = item === tab;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", String(active));
      item.tabIndex = active ? 0 : -1;
    });
    panel.setAttribute("aria-labelledby", tab.id);
    document.querySelector("#demo-title").textContent = view.title;
    document.querySelector("#demo-subtitle").textContent = view.subtitle;
    document.querySelector("#demo-stats").innerHTML = view.stats.map(([label, value, unit, note], index) => `<div><span>${label}</span><strong>${value}<small>${unit}</small></strong><em${index === 1 ? ' class="stat-blue"' : ""}>${note}</em></div>`).join("");
    document.querySelector("#demo-table-title").textContent = view.tableTitle;
    document.querySelector("#demo-table-head").innerHTML = `<tr>${view.headers.map((heading, index) => `<th scope="col"${index === 3 ? ' class="amount"' : ""}>${heading}</th>`).join("")}</tr>`;
    document.querySelector("#demo-table-body").innerHTML = view.rows.map(([name, detail, type, status, amount]) => `<tr><td><span class="document-mark">${icon(key === "boveda" ? "folder" : "file")}</span><span>${name}<small>${detail}</small></span></td><td>${type}</td><td><span class="pill ${key === "boveda" ? "pill-blue" : pillClass(status)}">${status}</span></td><td class="amount">${amount}</td></tr>`).join("");
  }

  const mobileTabs = window.matchMedia("(max-width: 560px)");
  const tablist = document.querySelector(".demo-tabs");
  function updateTabOrientation() {
    tablist.setAttribute("aria-orientation", mobileTabs.matches ? "horizontal" : "vertical");
  }
  updateTabOrientation();
  mobileTabs.addEventListener("change", updateTabOrientation);
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectView(tab));
    tab.addEventListener("keydown", (event) => {
      let nextIndex;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabs.length - 1;
      if (event.key === (mobileTabs.matches ? "ArrowRight" : "ArrowDown")) nextIndex = (index + 1) % tabs.length;
      if (event.key === (mobileTabs.matches ? "ArrowLeft" : "ArrowUp")) nextIndex = (index - 1 + tabs.length) % tabs.length;
      if (nextIndex === undefined) return;
      event.preventDefault();
      tabs[nextIndex].focus();
      selectView(tabs[nextIndex]);
    });
  });

  const menu = document.querySelector(".menu-toggle");
  const links = document.querySelector(".nav-links");
  function closeMenu() {
    menu.setAttribute("aria-expanded", "false");
    menu.setAttribute("aria-label", "Abrir menú");
    links.classList.remove("is-open");
  }
  menu.addEventListener("click", () => {
    const open = menu.getAttribute("aria-expanded") !== "true";
    menu.setAttribute("aria-expanded", String(open));
    menu.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
    links.classList.toggle("is-open", open);
  });
  links.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") {
      closeMenu();
      menu.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".nav")) closeMenu();
  });

  // Solo activa descargas con una URL HTTPS o un archivo relativo del sitio.
  function downloadUrl(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    const raw = value.trim();
    try {
      const url = new URL(raw, document.baseURI);
      if (url.protocol === "https:") return url;
      const relative = !/^[a-z][a-z\d+.-]*:/i.test(raw) && !raw.startsWith("//") && !raw.includes("\\");
      const localProtocol = ["file:", "http:", "https:"].includes(url.protocol);
      if (relative && localProtocol && url.origin === location.origin) return url;
    } catch {
      return null;
    }
    return null;
  }

  const config = window.CONXML_SITE || {};
  if (config.projectVersion) document.querySelectorAll("[data-project-version]").forEach((element) => { element.textContent = config.projectVersion; });
  let availablePackages = 0;
  document.querySelectorAll("[data-platform]").forEach((card) => {
    const platform = card.dataset.platform;
    const data = config.downloads?.[platform];
    const url = downloadUrl(data?.url);
    if (!url) return;
    const system = platform === "windows" ? "Windows" : "macOS";
    const button = card.querySelector(".download-button");
    button.href = url.href;
    button.removeAttribute("aria-disabled");
    button.removeAttribute("tabindex");
    button.classList.remove("is-disabled");
    button.querySelector("span").textContent = `Descargar para ${system}`;
    button.setAttribute("aria-label", `Descargar ConXml para ${system}${data.version ? `, versión ${data.version}` : ""}`);
    if (url.origin === location.origin) button.setAttribute("download", "");
    const status = card.querySelector(".download-state");
    status.textContent = "Disponible";
    status.classList.add("is-ready");
    card.querySelector(".package-info").textContent = data.fileName || `Paquete de ConXml para ${system}.`;
    card.querySelector(".download-meta").textContent = [data.version ? `Versión ${data.version}` : "", data.size || ""].filter(Boolean).join(" · ") || "Paquete listo para descargar";
    availablePackages += 1;
  });
  if (availablePackages) document.querySelector(".download-note").textContent = "Revisa los requisitos y las instrucciones incluidos con el paquete de tu sistema.";

  // La página permanece visible si JavaScript o el observador no están disponibles.
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  if ("IntersectionObserver" in window && !reducedMotion.matches) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
    document.documentElement.classList.add("js-reveal");
  }
})();
