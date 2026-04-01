const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');

const uz = document.getElementById('uploadZone');
const fi = document.getElementById('fileInput');
const ph = document.getElementById('ph');
const wrap = document.getElementById('wrap');
const overlay = document.getElementById('overlay');
const toastBox = document.getElementById('toast');

const calibrationMmInput = document.getElementById('calibrationMmInput');
const patternModeSelect = document.getElementById('patternModeSelect');
const manualPatternInput = document.getElementById('manualPatternInput');
const manualPatternBox = document.getElementById('manualPatternBox');
const referencePatternBox = document.getElementById('referencePatternBox');
const btnStartCalibration = document.getElementById('btnStartCalibration');
const btnAddReference = document.getElementById('btnAddReference');
const btnClearReferences = document.getElementById('btnClearReferences');
const btnMeasureInspection = document.getElementById('btnMeasureInspection');
const btnReset = document.getElementById('btnReset');
const optionalEfActions = document.getElementById('optionalEfActions');
const btnSaveCdOnly = document.getElementById('btnSaveCdOnly');
const btnContinueEf = document.getElementById('btnContinueEf');

const stepScale = document.getElementById('stepScale');
const stepPattern = document.getElementById('stepPattern');
const stepInspect = document.getElementById('stepInspect');

const abPxVal = document.getElementById('abPxVal');
const scaleVal = document.getElementById('scaleVal');
const referenceCountVal = document.getElementById('referenceCountVal');
const referenceMedianVal = document.getElementById('referenceMedianVal');
const activePatternVal = document.getElementById('activePatternVal');
const patternSourceVal = document.getElementById('patternSourceVal');
const patternPills = document.getElementById('patternPills');
const referenceList = document.getElementById('referenceList');
const inspectionCountVal = document.getElementById('inspectionCountVal');
const latestMeasurementVal = document.getElementById('latestMeasurementVal');
const diagnosticSummary = document.getElementById('diagnosticSummary');
const inspectionList = document.getElementById('inspectionList');
const reliabilityPills = document.getElementById('reliabilityPills');
const globalNotes = document.getElementById('globalNotes');

let img = null;
let state = 'idle'; // idle | calibA | calibB | refC | refD | refOptional | refE | refF | inspectC | inspectD | inspectOptional | inspectE | inspectF
let pendingPoint = null;
let pendingLink = null;
let calibration = { a:null, b:null, px:null, realMM:22.0, mmPerPx:null, center:null };
let manualPatternMM = 22.0;
let referenceLinks = [];
let inspections = [];

uz.onclick = () => fi.click();
uz.ondragover = e => { e.preventDefault(); uz.style.borderColor='var(--accent)'; };
uz.ondragleave = () => uz.style.borderColor='';
uz.ondrop = e => {
  e.preventDefault();
  uz.style.borderColor='';
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('image/')) loadImg(f);
};
fi.onchange = e => {
  const f = e.target.files[0];
  if (f) loadImg(f);
};

btnStartCalibration.onclick = () => {
  if (!img) return toast('Primero carga una imagen.');
  state = 'calibA';
  pendingPoint = null;
  pendingLink = null;
  showOverlay('Click en A: primer extremo del grillete de referencia');
  updateUI();
};

btnAddReference.onclick = () => {
  if (!calibration.mmPerPx) return toast('Primero calibra A-B.');
  startLinkCapture('reference');
  updateUI();
};

btnClearReferences.onclick = () => {
  referenceLinks = [];
  reanalyzeAll();
  updateUI();
  draw();
};

btnMeasureInspection.onclick = () => {
  if (!calibration.mmPerPx) return toast('Primero calibra A-B.');
  if (!getActivePattern()) return toast('Define un patrón activo antes de inspeccionar.');
  startLinkCapture('inspection');
  updateUI();
};

btnReset.onclick = () => resetAll();
btnSaveCdOnly.onclick = () => {
  if (state !== 'refOptional' && state !== 'inspectOptional') return;
  finalizeLinkCapture();
};
btnContinueEf.onclick = () => {
  if (!pendingLink) return;
  state = pendingLink.kind === 'reference' ? 'refE' : 'inspectE';
  showOptionalEfActions(false);
  showOverlay('Click en E: primer punto del lado derecho del mismo eslabón');
  draw();
};

calibrationMmInput.onchange = () => {
  calibration.realMM = sanitizePositiveNumber(calibrationMmInput.value, calibration.realMM);
  calibrationMmInput.value = calibration.realMM.toFixed(1);
  if (calibration.px) {
    calibration.mmPerPx = calibration.realMM / calibration.px;
    reanalyzeAll();
    toast(`Escala actualizada: 1 px = ${calibration.mmPerPx.toFixed(4)} mm.`);
  }
  updateUI();
};

manualPatternInput.onchange = () => {
  manualPatternMM = sanitizePositiveNumber(manualPatternInput.value, manualPatternMM);
  manualPatternInput.value = manualPatternMM.toFixed(1);
  reanalyzeAll();
  updateUI();
};

patternModeSelect.onchange = () => {
  const useRefs = patternModeSelect.value === 'references';
  manualPatternBox.style.display = useRefs ? 'none' : 'flex';
  referencePatternBox.style.display = useRefs ? 'flex' : 'none';
  reanalyzeAll();
  updateUI();
};

function loadImg(file) {
  const r = new FileReader();
  r.onload = e => {
    const i = new Image();
    i.onload = () => {
      img = i;
      const area = document.getElementById('canvasArea');
      const maxW = area.clientWidth - 40;
      const maxH = window.innerHeight - 160;
      const sc = Math.min(maxW / img.width, maxH / img.height, 1);
      cv.width = Math.round(img.width * sc);
      cv.height = Math.round(img.height * sc);
      ph.style.display = 'none';
      wrap.style.display = 'block';
      resetAll();
      draw();
      showOverlay('Empieza marcando A-B sobre el grillete de referencia');
      toast('Imagen cargada. Primer paso: calibrar A-B en el grillete.');
    };
    i.src = e.target.result;
  };
  r.readAsDataURL(file);
}

cv.onclick = e => {
  if (!img) return;
  const p = getCanvasPoint(e);

  if (state === 'calibA') {
    calibration.a = p;
    calibration.b = null;
    pendingPoint = p;
    state = 'calibB';
    showOverlay('Click en B: segundo extremo de la referencia');
    draw();
    return;
  }

  if (state === 'calibB') {
    calibration.b = p;
    pendingPoint = null;
    finalizeCalibration();
    return;
  }

  if (state === 'refC' || state === 'inspectC') return captureLinkPoint('c', p);
  if (state === 'refD' || state === 'inspectD') return captureLinkPoint('d', p);
  if (state === 'refE' || state === 'inspectE') return captureLinkPoint('e', p);
  if (state === 'refF' || state === 'inspectF') return captureLinkPoint('f', p);
};

function resetAll() {
  state = 'idle';
  pendingPoint = null;
  pendingLink = null;
  calibration = { a:null, b:null, px:null, realMM:sanitizePositiveNumber(calibrationMmInput.value, calibration.realMM), mmPerPx:null, center:null };
  manualPatternMM = sanitizePositiveNumber(manualPatternInput.value, manualPatternMM);
  calibrationMmInput.value = calibration.realMM.toFixed(1);
  manualPatternInput.value = manualPatternMM.toFixed(1);
  referenceLinks = [];
  inspections = [];
  hideOverlay();
  showOptionalEfActions(false);
  updateUI();
  draw();
}

function startLinkCapture(kind) {
  pendingPoint = null;
  pendingLink = { kind, c:null, d:null, e:null, f:null };
  state = kind === 'reference' ? 'refC' : 'inspectC';
  showOptionalEfActions(false);
  showOverlay(`Click en C: lado izquierdo del espesor del eslabón ${kind === 'reference' ? 'de referencia sana' : 'a inspeccionar'}`);
  draw();
}

function captureLinkPoint(key, point) {
  if (!pendingLink) return;
  pendingLink[key] = point;

  if (key === 'c') {
    state = pendingLink.kind === 'reference' ? 'refD' : 'inspectD';
    showOverlay('Click en D: cierra la medida del lado izquierdo (C-D)');
  } else if (key === 'd') {
    state = pendingLink.kind === 'reference' ? 'refOptional' : 'inspectOptional';
    showOptionalEfActions(true);
    showOverlay('C-D ya está medido. Puedes guardar así o seguir con E-F.');
  } else if (key === 'e') {
    state = pendingLink.kind === 'reference' ? 'refF' : 'inspectF';
    showOverlay('Click en F: cierra la medida del lado derecho (E-F)');
  } else if (key === 'f') {
    finalizeLinkCapture();
    return;
  }

  draw();
}

function finalizeCalibration() {
  calibration.realMM = sanitizePositiveNumber(calibrationMmInput.value, calibration.realMM);
  calibrationMmInput.value = calibration.realMM.toFixed(1);
  calibration.px = distancePx(calibration.a, calibration.b);
  if (calibration.px < 1) {
    calibration.a = null;
    calibration.b = null;
    calibration.px = null;
    state = 'idle';
    hideOverlay();
    showOptionalEfActions(false);
    updateUI();
    draw();
    toast('A y B están demasiado cerca. Marca una referencia con separación visible.');
    return;
  }
  calibration.mmPerPx = calibration.realMM / calibration.px;
  calibration.center = midpoint(calibration.a, calibration.b);
  state = 'idle';
  hideOverlay();
  showOptionalEfActions(false);
  reanalyzeAll();
  updateUI();
  draw();
  toast(`Escala definida: A-B = ${calibration.realMM.toFixed(1)} mm, 1 px = ${calibration.mmPerPx.toFixed(4)} mm.`);
}

function finalizeLinkCapture() {
  if (!pendingLink || !calibration.mmPerPx) return;
  const item = buildLinkMeasurement(pendingLink);
  if (!item) {
    pendingLink = null;
    state = 'idle';
    hideOverlay();
    showOptionalEfActions(false);
    draw();
    toast('La medida no es válida. Repite C-D y, si quieres, añade E-F.');
    return;
  }

  pendingLink = null;
  pendingPoint = null;
  state = 'idle';
  hideOverlay();
  showOptionalEfActions(false);

  if (item.kind === 'reference') {
    referenceLinks.push(item);
    toast(`Referencia sana ${referenceLinks.length}: crítico ${item.minSide} = ${item.minMm.toFixed(2)} mm.`);
  } else {
    inspections.push(analyzeInspection(item));
    toast(`Eslabón ${inspections.length}: crítico ${item.minSide} = ${item.minMm.toFixed(2)} mm.`);
  }

  reanalyzeAll();
  updateUI();
  draw();
}

function buildLinkMeasurement(link) {
  const cdPx = distancePx(link.c, link.d);
  const hasEf = !!(link.e && link.f);
  const hasPartialEf = (!!link.e && !link.f) || (!link.e && !!link.f);
  if (cdPx < 1 || hasPartialEf) return null;
  const efPx = hasEf ? distancePx(link.e, link.f) : null;
  if (hasEf && efPx < 1) return null;

  const cdMm = cdPx * calibration.mmPerPx;
  const efMm = hasEf ? efPx * calibration.mmPerPx : null;
  const minSide = !hasEf || cdMm <= efMm ? 'C-D' : 'E-F';
  const minMm = hasEf ? Math.min(cdMm, efMm) : cdMm;
  const centerCD = midpoint(link.c, link.d);
  const centerEF = hasEf ? midpoint(link.e, link.f) : null;

  return {
    id:`${Date.now()}-${Math.random().toString(16).slice(2,7)}`,
    kind: link.kind,
    c: link.c,
    d: link.d,
    e: link.e,
    f: link.f,
    cdPx,
    efPx,
    cdMm,
    efMm,
    hasEf,
    minSide,
    minMm,
    asymmetryPct: hasEf ? Math.abs(cdMm - efMm) / Math.max(cdMm, efMm) * 100 : 0,
    centerCD,
    centerEF,
    center: hasEf ? midpoint(centerCD, centerEF) : centerCD
  };
}

function reanalyzeAll() {
  if (!calibration.mmPerPx) return;
  referenceLinks = referenceLinks.map(i => buildLinkMeasurement(i));
  inspections = inspections.map(i => analyzeInspection(buildLinkMeasurement(i)));
  draw();
}

function analyzeInspection(item) {
  const pattern = getActivePattern();
  const perspective = getPerspective(item);
  if (!pattern) {
    return {
      ...item,
      cls:'s-info',
      title:'Patrón pendiente',
      detail:'Todavía no hay patrón activo para comparar.',
      cause:'Sin patrón activo; la app aún no puede decidir si el cambio aparente viene de desgaste o de material adherido.',
      confidence:{ level:'baja', label:'Confianza baja', reason:'Sin patrón activo para contrastar la medida.' },
      perspective
    };
  }

  const ratio = item.minMm / pattern;
  const diameterLossPct = Math.max(0, (1 - ratio) * 100);
  const sectionLossPct = Math.max(0, (1 - ratio * ratio) * 100);
  const overPct = Math.max(0, (ratio - 1) * 100);
  let cls = 's-ok';
  let title = 'Dentro de tolerancia';
  let detail = `${formatSides(item)} Crítico ${item.minSide} ${item.minMm.toFixed(2)} mm. Diámetro -${diameterLossPct.toFixed(1)}%, sección -${sectionLossPct.toFixed(1)}%.`;
  let cause = 'Sin desviación geométrica fuerte; aun así la medición no separa metal sano de óxido o biología adherida.';

  if (ratio < 0.85) {
    cls = 's-bad';
    title = 'Situación severa';
    cause = 'Espesor aparente claramente menor que el patrón: posible desgaste fuerte o corrosión con pérdida real de material.';
  } else if (ratio < 0.88) {
    cls = 's-bad';
    title = 'Bajo límite de renovación';
    cause = 'Espesor aparente menor que el patrón: probable desgaste o corrosión con pérdida de sección.';
  } else if (ratio < 0.92) {
    cls = 's-warn';
    title = 'Cerca del límite';
    cause = 'Ligera reducción de espesor: podría haber desgaste, corrosión o una toma de puntos algo conservadora.';
  } else if (ratio > 1.08) {
    cls = 's-warn';
    title = 'Mayor que el patrón';
    detail = `${formatSides(item)} Crítico ${item.minSide} ${item.minMm.toFixed(2)} mm. ${overPct.toFixed(1)}% por encima del patrón; revisa incrustación, biología o puntos de clic.`;
    cause = 'Espesor aparente mayor que el patrón: posible biología marina adherida, incrustación, óxido superficial o puntos tomados sobre material pegado.';
  }

  if (item.hasEf && item.asymmetryPct > 10) {
    detail += ` Diferencia entre lados ${item.asymmetryPct.toFixed(1)}%: puede haber desgaste localizado o perspectiva.`;
    cause += ' La asimetría entre C-D y E-F sugiere además adherencia o desgaste localizado.';
  }
  if (perspective.level === 'media') detail += ' Posible efecto de perspectiva: está algo alejado de la referencia.';
  if (perspective.level === 'alta') {
    detail += ' Riesgo alto de perspectiva: usa una referencia más cercana o una foto más perpendicular.';
    if (cls === 's-ok') cls = 's-warn';
  }

  const confidence = getMeasurementConfidence({ ratio, overPct, asymmetryPct:item.asymmetryPct, perspective });
  return { ...item, cls, title, detail, cause, confidence, perspective };
}

function getMeasurementConfidence({ ratio, overPct, asymmetryPct, perspective }) {
  let score = 100;
  const reasons = [];

  if (asymmetryPct > 25) {
    score -= 45;
    reasons.push(`asimetría muy alta entre C-D y E-F (${asymmetryPct.toFixed(1)}%)`);
  } else if (asymmetryPct > 12) {
    score -= 25;
    reasons.push(`asimetría apreciable entre lados (${asymmetryPct.toFixed(1)}%)`);
  }

  if (perspective.level === 'alta') {
    score -= 35;
    reasons.push('perspectiva alta');
  } else if (perspective.level === 'media') {
    score -= 15;
    reasons.push('perspectiva media');
  }

  if (ratio > 1.08) {
    score -= 20;
    reasons.push(`sobreespesor aparente ${overPct.toFixed(1)}% sobre el patrón`);
  }

  let level = 'alta';
  let label = 'Confianza alta';
  if (score < 45) {
    level = 'baja';
    label = 'Confianza baja';
  } else if (score < 75) {
    level = 'media';
    label = 'Confianza media';
  }

  const reason = reasons.length
    ? `Reducida por ${reasons.join(', ')}.`
    : 'C-D y E-F son consistentes y la geometría visible no muestra alertas fuertes.';

  return { level, label, reason, score };
}

function getPerspective(item) {
  if (!img || !calibration.center) return { level:'desconocida', text:'Sin referencia espacial' };
  const anchor = getAnchor(item.center);
  const norm = distancePx(item.center, anchor) / Math.hypot(cv.width, cv.height);
  if (norm < 0.14) return { level:'baja', text:'Muy cerca de la referencia visual' };
  if (norm < 0.28) return { level:'media', text:'Separación media respecto a la referencia' };
  return { level:'alta', text:'Muy lejos de la referencia en la imagen' };
}

function getAnchor(center) {
  if (patternModeSelect.value === 'references' && referenceLinks.length) {
    return referenceLinks.reduce((best, item) => {
      if (!best) return item.center;
      return distancePx(center, item.center) < distancePx(center, best) ? item.center : best;
    }, null);
  }
  return calibration.center;
}

function getActivePattern() {
  if (patternModeSelect.value === 'manual') return manualPatternMM;
  if (!referenceLinks.length) return null;
  return getMedian(referenceLinks.map(i => i.minMm));
}

function getMedian(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a,b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function draw() {
  ctx.clearRect(0,0,cv.width,cv.height);
  if(!img) return;
  ctx.drawImage(img,0,0,cv.width,cv.height);

  if (calibration.a) drawPt(calibration.a,'#00e5ff','A');
  if (calibration.b) drawPt(calibration.b,'#00e5ff','B');
  if (calibration.a && calibration.b) {
    drawLine(calibration.a, calibration.b, '#00e5ff');
    midLabel(calibration.a, calibration.b, calibration.mmPerPx ? `A-B ${calibration.realMM.toFixed(1)}mm` : `A-B ${calibration.px.toFixed(1)}px`, '#00e5ff');
  }

  referenceLinks.forEach((i, idx) => drawLinkItem(i, '#39ff14', `R${idx+1}`));
  inspections.forEach((i, idx) => drawLinkItem(i, getStatusColor(i.cls), `M${idx+1}`));

  if (pendingLink) drawPendingLink();
  else if (pendingPoint) drawPt(pendingPoint, '#facc15', '?');
}

function drawPt(p,col,lbl) {
  ctx.beginPath(); ctx.arc(p.x,p.y,10,0,Math.PI*2); ctx.fillStyle=col+'22'; ctx.fill();
  ctx.beginPath(); ctx.arc(p.x,p.y,5,0,Math.PI*2); ctx.fillStyle=col; ctx.fill();
  ctx.strokeStyle=col; ctx.lineWidth=1.5;
  ctx.beginPath(); ctx.moveTo(p.x-9,p.y); ctx.lineTo(p.x+9,p.y); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(p.x,p.y-9); ctx.lineTo(p.x,p.y+9); ctx.stroke();
  ctx.fillStyle=col; ctx.font='bold 11px Space Mono,monospace';
  ctx.fillText(lbl,p.x+8,p.y-8);
}

function drawLine(p1,p2,col) {
  ctx.beginPath(); ctx.moveTo(p1.x,p1.y); ctx.lineTo(p2.x,p2.y);
  ctx.strokeStyle=col; ctx.lineWidth=2; ctx.stroke();
}

function midLabel(p1,p2,txt,col) {
  const mx=(p1.x+p2.x)/2, my=(p1.y+p2.y)/2;
  ctx.font='bold 10px Space Mono,monospace';
  const w=ctx.measureText(txt).width+10;
  ctx.fillStyle='rgba(10,12,16,.85)';
  ctx.beginPath(); ctx.roundRect(mx-w/2,my-12,w,18,4); ctx.fill();
  ctx.fillStyle=col; ctx.textAlign='center'; ctx.fillText(txt,mx,my+2); ctx.textAlign='left';
}

function getCanvasPoint(e) {
  const rect = cv.getBoundingClientRect();
  const scaleX = cv.width / rect.width;
  const scaleY = cv.height / rect.height;
  return { x:(e.clientX - rect.left) * scaleX, y:(e.clientY - rect.top) * scaleY };
}

function distancePx(p1,p2) {
  return Math.hypot(p2.x - p1.x, p2.y - p1.y);
}

function midpoint(p1,p2) {
  return { x:(p1.x + p2.x) / 2, y:(p1.y + p2.y) / 2 };
}

function sanitizePositiveNumber(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function getStatusColor(cls) {
  if (cls === 's-bad') return '#ff3b3b';
  if (cls === 's-warn') return '#ffb800';
  if (cls === 's-ok') return '#39ff14';
  return '#00e5ff';
}

function drawLinkItem(item, color, prefix) {
  drawPt(item.c, color, `${prefix}c`);
  drawPt(item.d, color, `${prefix}d`);
  drawLine(item.c, item.d, color);
  midLabel(item.c, item.d, `CD ${item.cdMm.toFixed(1)}mm`, color);

  if (!item.hasEf) return;
  drawPt(item.e, color, `${prefix}e`);
  drawPt(item.f, color, `${prefix}f`);
  drawLine(item.e, item.f, color);
  midLabel(item.e, item.f, `EF ${item.efMm.toFixed(1)}mm`, color);
}

function drawPendingLink() {
  const color = '#facc15';
  if (pendingLink.c) drawPt(pendingLink.c, color, 'C');
  if (pendingLink.d) drawPt(pendingLink.d, color, 'D');
  if (pendingLink.c && pendingLink.d) drawLine(pendingLink.c, pendingLink.d, color);
  if (pendingLink.e) drawPt(pendingLink.e, color, 'E');
  if (pendingLink.f) drawPt(pendingLink.f, color, 'F');
  if (pendingLink.e && pendingLink.f) drawLine(pendingLink.e, pendingLink.f, color);
}

function updateUI() {
  const scaleReady = !!calibration.mmPerPx;
  const pattern = getActivePattern();
  const patternReady = !!pattern;
  const latest = inspections[inspections.length - 1];

  const useRefs = patternModeSelect.value === 'references';
  manualPatternBox.style.display = useRefs ? 'none' : 'flex';
  referencePatternBox.style.display = useRefs ? 'flex' : 'none';

  stepScale.className = 'step';
  stepPattern.className = 'step';
  stepInspect.className = 'step';
  if (!scaleReady) stepScale.classList.add('active');
  else {
    stepScale.classList.add('done');
    if (!patternReady) stepPattern.classList.add('active');
    else {
      stepPattern.classList.add('done');
      stepInspect.classList.add(inspections.length ? 'done' : 'active');
    }
  }

  btnAddReference.disabled = !scaleReady;
  btnClearReferences.disabled = !referenceLinks.length;
  btnMeasureInspection.disabled = !(scaleReady && patternReady);

  abPxVal.textContent = calibration.px ? `${calibration.px.toFixed(1)} px` : '— px';
  scaleVal.textContent = calibration.mmPerPx ? `${calibration.mmPerPx.toFixed(4)}` : '— mm/px';
  referenceCountVal.textContent = `${referenceLinks.length}`;
  referenceMedianVal.textContent = referenceLinks.length ? `${getMedian(referenceLinks.map(i => i.minMm)).toFixed(2)} mm` : '— mm';
  activePatternVal.textContent = patternReady ? `${pattern.toFixed(2)} mm` : '— mm';
  patternSourceVal.textContent = patternModeSelect.value === 'manual' ? 'Manual' : (referenceLinks.length ? 'Mediana' : 'Pendiente');
  inspectionCountVal.textContent = `${inspections.length}`;
  latestMeasurementVal.textContent = latest ? `${latest.minMm.toFixed(2)} mm` : '— mm';

  renderPatternPills(scaleReady, patternReady);
  renderReferenceList();
  renderInspectionList();
  renderDiagnostic(latest, patternReady);
  renderReliability(latest, scaleReady, patternReady);
}

function renderPatternPills(scaleReady, patternReady) {
  const pills = [];
  pills.push(`<span class="pill ${scaleReady ? 'ok' : 'warn'}">${scaleReady ? 'Escala lista' : 'Falta A-B'}</span>`);
  pills.push(`<span class="pill ${patternModeSelect.value === 'manual' ? 'info' : (referenceLinks.length >= 3 ? 'ok' : 'warn')}">${patternModeSelect.value === 'manual' ? 'Nominal manual' : `Sanos(min): ${referenceLinks.length}`}</span>`);
  pills.push(`<span class="pill ${patternReady ? 'ok' : 'warn'}">${patternReady ? 'Patrón activo' : 'Patrón pendiente'}</span>`);
  patternPills.innerHTML = pills.join('');
}

function renderReferenceList() {
  if (!referenceLinks.length) {
    referenceList.innerHTML = '<div class="empty">No hay eslabones sanos cargados. Recomendado: al menos 3 eslabones que se vean mejor conservados. El primero junto al grillete no se asume sano automáticamente.</div>';
    return;
  }
  referenceList.innerHTML = referenceLinks.map((i, idx) => `
    <div class="list-card">
      <h5>Referencia sana ${idx + 1}</h5>
      <p>${i.hasEf ? `C-D ${i.cdMm.toFixed(2)} mm | E-F ${i.efMm.toFixed(2)} mm` : `C-D ${i.cdMm.toFixed(2)} mm`}</p>
      <p>Crítico ${i.minSide}: ${i.minMm.toFixed(2)} mm</p>
    </div>
  `).join('');
}

function renderInspectionList() {
  if (!inspections.length) {
    inspectionList.innerHTML = '';
    return;
  }
  inspectionList.innerHTML = inspections.map((i, idx) => `
    <div class="list-card">
      <h5>Eslabón ${idx + 1} · crítico ${i.minMm.toFixed(2)} mm</h5>
      <span class="status ${i.cls}">${i.title}</span>
      <p class="compact-line">${i.hasEf ? `C-D ${i.cdMm.toFixed(2)} mm · E-F ${i.efMm.toFixed(2)} mm` : `C-D ${i.cdMm.toFixed(2)} mm`} · ${formatDelta(i)} · ${summarizeCause(i)}</p>
      <details class="detail-toggle">
        <summary>Ver detalle</summary>
        <div class="detail-body">
          <p>${i.hasEf ? `C-D ${i.cdMm.toFixed(2)} mm · E-F ${i.efMm.toFixed(2)} mm` : `C-D ${i.cdMm.toFixed(2)} mm`} · crítico ${i.minSide} ${i.minMm.toFixed(2)} mm</p>
          <p>${formatDelta(i)}</p>
          <p>Posible causa: ${summarizeCause(i)}</p>
        </div>
      </details>
    </div>
  `).join('');
}

function renderDiagnostic(latest, patternReady) {
  if (!inspections.length) {
    diagnosticSummary.className = 'empty';
    diagnosticSummary.textContent = patternReady ? 'Patrón listo. Ya puedes medir eslabones con C-D y E-F.' : 'Todavía no hay inspecciones.';
    return;
  }
  diagnosticSummary.className = 'list-card';
  diagnosticSummary.innerHTML = `
    <h5>Último diagnóstico</h5>
    <span class="status ${latest.cls}">${latest.title}</span>
    <p class="compact-line">${latest.hasEf ? `C-D ${latest.cdMm.toFixed(2)} mm · E-F ${latest.efMm.toFixed(2)} mm` : `C-D ${latest.cdMm.toFixed(2)} mm`} · crítico ${latest.minSide} ${latest.minMm.toFixed(2)} mm</p>
    <p class="compact-line">${formatDelta(latest)} · ${summarizeCause(latest)}</p>
    <details class="detail-toggle">
      <summary>Ver detalle</summary>
      <div class="detail-body">
        <p>${latest.hasEf ? `C-D ${latest.cdMm.toFixed(2)} mm · E-F ${latest.efMm.toFixed(2)} mm` : `C-D ${latest.cdMm.toFixed(2)} mm`}</p>
        <p>${formatDelta(latest)}</p>
        <p>Posible causa: ${summarizeCause(latest)}</p>
      </div>
    </details>
  `;
}

function renderReliability(latest, scaleReady, patternReady) {
  const pills = [];
  pills.push(`<span class="pill ${scaleReady ? 'ok' : 'warn'}">${scaleReady ? 'Escala calibrada' : 'Escala pendiente'}</span>`);
  pills.push(`<span class="pill ${patternReady ? 'ok' : 'warn'}">${patternReady ? 'Patrón definido' : 'Sin patrón'}</span>`);
  if (patternModeSelect.value === 'references') {
    pills.push(`<span class="pill ${referenceLinks.length >= 3 ? 'ok' : 'warn'}">${referenceLinks.length >= 3 ? 'Muestra sana razonable' : 'Pocas referencias'}</span>`);
  } else {
    pills.push('<span class="pill info">Comparación contra nominal manual</span>');
  }
  if (latest) {
    const cls = latest.perspective.level === 'alta' ? 'bad' : latest.perspective.level === 'media' ? 'warn' : 'ok';
    pills.push(`<span class="pill ${cls}">Perspectiva ${latest.perspective.level}</span>`);
    const confCls = latest.confidence.level === 'baja' ? 'bad' : latest.confidence.level === 'media' ? 'warn' : 'ok';
    pills.push(`<span class="pill ${confCls}">${latest.confidence.label}</span>`);
  }
  reliabilityPills.innerHTML = pills.join('');
  globalNotes.textContent = latest && latest.perspective.level === 'alta'
    ? 'Aviso fuerte: el último eslabón está muy lejos de la referencia en la imagen. La diferencia podría venir de profundidad, no solo de desgaste.'
    : latest
      ? `${latest.confidence.label}: ${latest.confidence.reason}`
      : 'En mediana sana se usa el menor entre C-D y E-F de cada eslabón sano. La perspectiva aquí es una heurística, no una reconstrucción 3D real.';
}

function formatDelta(item) {
  if (!item || !Number.isFinite(item.minMm)) return 'Sin medida';
  const pattern = getActivePattern();
  if (!pattern) return 'Sin patrón activo';
  const deltaPct = ((item.minMm / pattern) - 1) * 100;
  if (Math.abs(deltaPct) < 0.5) return '0.0% respecto al patrón';
  return `${deltaPct > 0 ? '+' : ''}${deltaPct.toFixed(1)}% respecto al patrón`;
}

function summarizeCause(item) {
  const pattern = getActivePattern();
  if (!pattern) return 'Aún no hay referencia para interpretar la medida';
  const ratio = item.minMm / pattern;
  if (ratio > 1.08) return 'más mm que el patrón: posible biología, incrustación u óxido superficial';
  if (ratio < 0.92) return 'menos mm que el patrón: posible desgaste o corrosión';
  return 'muy parecido al patrón';
}

function formatSides(item) {
  if (!item.hasEf) return `C-D ${item.cdMm.toFixed(2)} mm.`;
  return `C-D ${item.cdMm.toFixed(2)} mm, E-F ${item.efMm.toFixed(2)} mm.`;
}

function showOptionalEfActions(visible) {
  optionalEfActions.style.display = visible ? 'grid' : 'none';
}

function showOverlay(msg) {
  overlay.innerHTML = `<span>${msg}</span>`;
  overlay.classList.add('show');
}

function hideOverlay() {
  overlay.classList.remove('show');
}

function toast(msg) {
  toastBox.textContent = msg;
  toastBox.classList.add('show');
  clearTimeout(toastBox._t);
  toastBox._t = setTimeout(() => toastBox.classList.remove('show'), 4500);
}

updateUI();
