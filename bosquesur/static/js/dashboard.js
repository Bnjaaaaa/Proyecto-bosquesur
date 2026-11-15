/* Gráficos del dashboard gerencial (Chart.js 4). Los datos vienen del servidor vía json_script. */
(function () {
  const datos = JSON.parse(document.getElementById("datos-dashboard").textContent);
  const tolerancia = parseFloat(JSON.parse(document.getElementById("tolerancia").textContent));
  const num = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 });
  const fechaCorta = (iso) => { const [a, m, d] = iso.split("-"); return d + "-" + m; };

  const COLOR = {
    enviado: "#2a78d6",   // serie 1 (paleta categórica validada para daltonismo)
    recibido: "#eb6834",  // serie 2
    barra: "#2f5d3a",     // serie única: color de marca
    referencia: "#8a8a80",
    tinta: "#55605a",
    grilla: "#e6e6de",
  };

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = COLOR.tinta;
  Chart.defaults.plugins.tooltip.backgroundColor = "#1f2620";
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.plugins.legend.labels.boxHeight = 12;
  Chart.defaults.maintainAspectRatio = false;

  const ejeY = (titulo) => ({
    beginAtZero: true,
    grid: { color: COLOR.grilla },
    border: { display: false },
    title: { display: !!titulo, text: titulo },
    ticks: { callback: (v) => num.format(v) },
  });
  const ejeX = { grid: { display: false }, border: { color: COLOR.grilla } };

  // 1) Enviado vs recibido por día
  new Chart(document.getElementById("g-serie"), {
    type: "line",
    data: {
      labels: datos.serie_diaria.map((d) => fechaCorta(d.fecha)),
      datasets: [
        { label: "Enviado (guía)", data: datos.serie_diaria.map((d) => d.enviado), borderColor: COLOR.enviado,
          backgroundColor: COLOR.enviado, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, cubicInterpolationMode: "monotone" },
        { label: "Recibido (patio)", data: datos.serie_diaria.map((d) => d.recibido), borderColor: COLOR.recibido,
          backgroundColor: COLOR.recibido, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, cubicInterpolationMode: "monotone",
          borderDash: [6, 3] },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", align: "start" },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${num.format(c.parsed.y)} m³` } },
      },
      scales: { x: ejeX, y: ejeY("m³") },
    },
  });

  // 2) Merma por faena con línea de tolerancia
  const faenas = datos.discrepancia_por_faena;
  new Chart(document.getElementById("g-faena"), {
    data: {
      labels: faenas.map((f) => f.faena),
      datasets: [
        { type: "bar", label: "Merma %", data: faenas.map((f) => f.porcentaje), backgroundColor: COLOR.barra,
          borderRadius: 4, maxBarThickness: 48 },
        { type: "line", label: `Tolerancia ${num.format(tolerancia)}%`, data: faenas.map(() => tolerancia),
          borderColor: COLOR.referencia, borderDash: [4, 4], borderWidth: 2, pointRadius: 0 },
      ],
    },
    options: {
      plugins: {
        legend: { position: "top", align: "start" },
        tooltip: { callbacks: { label: (c) => c.dataset.type === "line"
          ? ` Tolerancia: ${num.format(c.parsed.y)}%`
          : ` Merma: ${num.format(c.parsed.y)}% (${faenas[c.dataIndex].guias} guías)` } },
      },
      scales: { x: ejeX, y: ejeY("%") },
    },
  });

  // 3) Stock actual por producto (barras horizontales, una sola serie)
  const stock = datos.stock_por_producto;
  new Chart(document.getElementById("g-stock"), {
    type: "bar",
    data: {
      labels: stock.map((s) => s.producto),
      datasets: [{ label: "Stock (m³)", data: stock.map((s) => s.cantidad), backgroundColor: COLOR.barra,
        borderRadius: 4, maxBarThickness: 28 }],
    },
    options: {
      indexAxis: "y",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => ` ${num.format(c.parsed.x)} m³` } },
      },
      scales: { x: ejeY("m³"), y: { grid: { display: false }, border: { display: false } } },
    },
  });
})();
