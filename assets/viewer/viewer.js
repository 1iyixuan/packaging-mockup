const viewer = document.querySelector('model-viewer');
const flat = document.querySelector('#flat-view');
const artwork = flat.querySelector('img');
const stage = document.querySelector('#fold-stage');
const flatButton = document.querySelector('#show-flat');
const modelButton = document.querySelector('#show-model');
const fullscreen = document.querySelector('.fullscreen');
const status = document.querySelector('#load-status');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const narrow = matchMedia('(max-aspect-ratio: 4/5)');
const revision = document.body.dataset.revision;
const foldConfig = document.body.dataset.foldConfig;
const fold = foldConfig ? loadFold() : Promise.resolve(null);
const pointers = new Map();
let activePointerType;
let zoom = 1;
let panX = 0;
let panY = 0;
let view = 'model';
let switching = false;
let savedOrbit;
let savedFieldOfView;
let clean = false;

const timeout = setTimeout(() => fail('模型加载超时，请刷新重试。'), 45000);

function initialOrbit() {
  return narrow.matches ? viewer.dataset.mobileOrbit : viewer.dataset.initialOrbit;
}

viewer.setAttribute('camera-orbit', initialOrbit());
narrow.addEventListener('change', () => {
  if (view === 'model' && !switching) viewer.cameraOrbit = initialOrbit();
});

function fail(message) {
  clearTimeout(timeout);
  status.textContent = message;
  status.hidden = false;
}

viewer.addEventListener('load', () => {
  clearTimeout(timeout);
  status.hidden = true;
  viewer.dataset.loaded = 'true';
  modelButton.disabled = false;
});
viewer.addEventListener('error', () => fail('模型未能加载，请刷新重试。'));
if (artwork.hasAttribute('src')) {
  artwork.decode().then(() => {
    flatButton.disabled = false;
  }).catch(() => {
    flatButton.title = '展开图未能加载';
  });
}

async function loadFold() {
  try {
    const [{ createFold }, response] = await Promise.all([
      import(`./fold.js?v=${revision}`),
      fetch(foldConfig),
    ]);
    if (!response.ok) throw new Error(`折叠配置加载失败（${response.status}）`);
    return createFold(stage, await response.json(), artwork.getAttribute('src'));
  } catch (error) {
    console.warn('折叠动画不可用，改为直接切换。', error);
    return null;
  }
}

function paintFlat() {
  artwork.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
}

function zoomAt(value, x = 0, y = 0) {
  const nextZoom = Math.max(0.45, Math.min(6, value));
  const ratio = nextZoom / zoom;
  panX = x + (panX - x) * ratio;
  panY = y + (panY - y) * ratio;
  zoom = nextZoom;
}

function relativeToFlatCenter(clientX, clientY) {
  const bounds = flat.getBoundingClientRect();
  return [clientX - bounds.left - bounds.width / 2, clientY - bounds.top - bounds.height / 2];
}

function pointerFrame() {
  const [[x, y], second] = pointers.values();
  if (!second) return { x, y, distance: 0 };
  const [otherX, otherY] = second;
  return {
    x: (x + otherX) / 2,
    y: (y + otherY) / 2,
    distance: Math.hypot(x - otherX, y - otherY),
  };
}

flat.addEventListener('pointerdown', event => {
  if (event.button !== 0 || pointers.size === 2) return;
  if (pointers.size && (event.pointerType !== 'touch' || activePointerType !== 'touch')) return;
  flat.setPointerCapture(event.pointerId);
  activePointerType = event.pointerType;
  pointers.set(event.pointerId, [event.clientX, event.clientY]);
  flat.classList.add('is-dragging');
});
flat.addEventListener('pointermove', event => {
  if (!pointers.has(event.pointerId)) return;
  const before = pointerFrame();
  pointers.set(event.pointerId, [event.clientX, event.clientY]);
  const after = pointerFrame();
  if (before.distance > 1 && after.distance > 1) {
    const [x, y] = relativeToFlatCenter(before.x, before.y);
    zoomAt(zoom * after.distance / before.distance, x, y);
  }
  panX += after.x - before.x;
  panY += after.y - before.y;
  paintFlat();
});
function releasePointer(event) {
  pointers.delete(event.pointerId);
  flat.classList.toggle('is-dragging', pointers.size > 0);
}
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) flat.addEventListener(event, releasePointer);
flat.addEventListener('wheel', event => {
  event.preventDefault();
  const amount = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 120 : 1);
  const [x, y] = relativeToFlatCenter(event.clientX, event.clientY);
  zoomAt(zoom * Math.exp(-amount * .0017), x, y);
  paintFlat();
}, { passive: false });

flat.addEventListener('keydown', event => {
  switch (event.key) {
    case 'ArrowUp':
    case '+':
    case '=': zoomAt(zoom * 1.15); break;
    case 'ArrowDown':
    case '-': zoomAt(zoom / 1.15); break;
    case 'Home': zoom = 1; panX = 0; panY = 0; break;
    default: return;
  }
  event.preventDefault();
  paintFlat();
});

viewer.addEventListener('keydown', event => {
  if (event.key !== 'Home') return;
  event.preventDefault();
  viewer.cameraOrbit = initialOrbit();
  viewer.cameraTarget = 'auto auto auto';
  viewer.fieldOfView = '30deg';
  if (reducedMotion.matches) viewer.jumpCameraToGoal();
});

function animate(duration, frame) {
  return new Promise(resolve => {
    let start;
    function update(now) {
      start ??= now;
      const progress = Math.min(1, (now - start) / duration);
      frame(progress);
      if (progress < 1) requestAnimationFrame(update);
      else resolve();
    }
    requestAnimationFrame(update);
  });
}

function closedFrame() {
  const bounds = viewer.getBoundingClientRect();
  const { radius, theta, phi } = viewer.getCameraOrbit();
  const field = viewer.getFieldOfView() * Math.PI / 180;
  const perspective = bounds.height / (2 * Math.tan(field / 2));
  return {
    pixelsPerUnit: perspective / radius,
    perspective,
    offsetX: bounds.left + bounds.width / 2 - window.innerWidth / 2,
    offsetY: bounds.top + bounds.height / 2 - window.innerHeight / 2,
    modelHeight: viewer.getDimensions().y,
    tilt: phi * 180 / Math.PI - 90,
    turn: -theta * 180 / Math.PI,
  };
}

async function switchView(next) {
  if (next === view || switching) return;
  switching = true;
  const toFlat = next === 'flat';
  const loaded = viewer.dataset.loaded === 'true';
  if (toFlat && loaded) {
    savedOrbit = viewer.getCameraOrbit().toString();
    savedFieldOfView = viewer.getFieldOfView() + 'deg';
  }
  const renderFold = loaded && !reducedMotion.matches ? await fold : null;

  if (renderFold) {
    viewer.removeAttribute('camera-controls');
    viewer.cameraOrbit = initialOrbit();
    viewer.fieldOfView = '30deg';
    if (toFlat) await animate(260, () => {});
    viewer.jumpCameraToGoal();
    const closed = closedFrame();
    stage.style.perspective = closed.perspective + 'px';
    flat.hidden = false;
    const open = { width: artwork.offsetWidth, zoom, panX, panY };
    flat.hidden = true;
    renderFold(toFlat ? 0 : 1, closed, open);
    stage.hidden = false;
    document.body.dataset.view = 'folding';
    await animate(1050, progress => renderFold(toFlat ? progress : 1 - progress, closed, open));
    stage.hidden = true;
  }

  view = next;
  document.body.dataset.view = view;
  flat.hidden = !toFlat;
  viewer.tabIndex = toFlat ? -1 : 0;
  flatButton.setAttribute('aria-pressed', String(toFlat));
  modelButton.setAttribute('aria-pressed', String(!toFlat));
  if (!toFlat && viewer.dataset.loaded === 'true') {
    viewer.setAttribute('camera-controls', '');
    if (savedOrbit) viewer.cameraOrbit = savedOrbit;
    if (savedFieldOfView) viewer.fieldOfView = savedFieldOfView;
    if (reducedMotion.matches) viewer.jumpCameraToGoal();
  }
  switching = false;
}

flatButton.addEventListener('click', () => void switchView('flat'));
modelButton.addEventListener('click', () => void switchView('model'));

function setClean(value) {
  clean = value;
  document.body.toggleAttribute('data-clean', clean);
  fullscreen.setAttribute('aria-pressed', String(clean));
  const label = clean ? '退出全屏' : '全屏展示';
  fullscreen.setAttribute('aria-label', label);
  fullscreen.title = label;
}
fullscreen.addEventListener('click', async () => {
  if (clean) {
    setClean(false);
    if (document.fullscreenElement) await document.exitFullscreen().catch(() => {});
  } else {
    setClean(true);
    await document.documentElement.requestFullscreen?.().catch(() => {});
  }
});
document.addEventListener('fullscreenchange', () => {
  if (!document.fullscreenElement) setClean(false);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && clean && !document.fullscreenElement) setClean(false);
});

import(`./vendor/model-viewer.min.js?v=${revision}`).catch(() => fail('三维查看器未能加载，请刷新重试。'));
