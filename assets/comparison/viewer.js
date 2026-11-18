const scene = document.querySelector('#model-stage');
const back = document.querySelector('#back-to-compare');
const compareTitle = document.querySelector('#compare-title');
const help = document.querySelector('#orbit-help');
const comparisonHelp = help.textContent;
const settings = JSON.parse(document.body.dataset.comparison);
const names = settings.schemes.map(scheme => scheme.name);
const shared = document.querySelector('#shared-viewer');
const models = [...shared.querySelectorAll('extra-model')];
const modelPair = document.querySelector('.model-pair');
const shortcuts = document.querySelector('.scheme-shortcuts');
const width = settings.dimensions_mm[0] / 1000;
const height = settings.dimensions_mm[2] / 1000;
const spacing = width * 1.65;
const centers = names.map((_, i) => (i - (names.length - 1) / 2) * spacing);
const boxHeight = height;
const sharedHalfFov = Math.PI / 30;
const viewers = [...modelPair.querySelectorAll('model-viewer')];
const flat = document.querySelector('#flat-view');
const pair = flat.querySelector('.artwork-pair');
const images = [...pair.querySelectorAll('img')];
const stage = document.querySelector('#fold-stage');
const surfaces = [...stage.children];
const flatButton = document.querySelector('#show-flat');
const modelButton = document.querySelector('#show-model');
const fullscreen = document.querySelector('.fullscreen');
const status = document.querySelector('#load-status');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const desktopPointer = matchMedia('(hover: hover) and (pointer: fine)');
const revision = document.body.dataset.revision;
const initial = { theta: 16 * Math.PI / 180, phi: 80 * Math.PI / 180, fov: 30 };
const states = viewers.map(() => ({...initial}));
const all = viewers.map((_, i) => i);
const ready = new Set();
const failed = new Set();
let foldAssets;
let view = 'model';
let switching = false;
let clean = false;
let zoom = 1;
let panX = 0;
let panY = 0;
let lastRotated = 0;
let selected = null;
let comparisonCamera;
let comparisonFlat;
let hovered = -1;
let sharedReady = false;
let sharedFailed = false;
let sharedScale = 1;
const displayedScales = models.map(() => 1);
let scaleAnimation = 0;
let sharedRadius = 1;

function visibleModels() {
  return selected === null ? all : [selected];
}

function paintSharedModel(i) {
  if (!sharedReady) return;
  const {theta, phi} = states[i];
  const yaw = -theta;
  const tilt = Math.PI / 2 - phi;
  // Convert Rx(tilt) * Ry(yaw) to the viewer's YXZ Euler order.
  const x = Math.asin(Math.sin(tilt) * Math.cos(yaw));
  const y = Math.atan2(Math.sin(yaw), Math.cos(tilt) * Math.cos(yaw));
  const z = Math.atan2(Math.sin(tilt) * Math.sin(yaw), Math.cos(tilt));
  const scale = displayedScales[i];
  const half = boxHeight * scale / 2;
  models[i].orientation = z + 'rad ' + x + 'rad ' + y + 'rad';
  models[i].offset = centers[i] + 'm ' + (-half * Math.cos(tilt)) + 'm ' + (-half * Math.sin(tilt)) + 'm';
  models[i].scale = String(scale);
}

function animateSharedScale() {
  cancelAnimationFrame(scaleAnimation);
  const from = [...displayedScales];
  const target = all.map(i => sharedScale * (i === hovered ? 1.045 : 1));
  const changing = all.filter(i => from[i] !== target[i]);
  if (!changing.length) return;

  function apply(progress) {
    for (const i of changing) {
      displayedScales[i] = progress === 1 ? target[i] : from[i] + (target[i] - from[i]) * progress;
      paintSharedModel(i);
    }
  }

  if (reducedMotion.matches) {
    apply(1);
    return;
  }

  const start = performance.now();
  function frame(now) {
    const elapsed = Math.min(1, (now - start) / 170);
    apply(1 - (1 - elapsed) ** 3);
    if (elapsed < 1) scaleAnimation = requestAnimationFrame(frame);
  }
  scaleAnimation = requestAnimationFrame(frame);
}

function setHover(index) {
  if (hovered === index) return;
  hovered = index;
  scene.toggleAttribute('data-hover', index >= 0);
  animateSharedScale();
}

function fitShared() {
  if (!sharedReady || !shared.clientWidth || !shared.clientHeight) return;
  const aspect = shared.clientWidth / shared.clientHeight;
  const visibleHeight = Math.max(boxHeight * 1.77, (spacing * (names.length - 1) + width * 2.24) / aspect);
  sharedRadius = visibleHeight / (2 * Math.tan(sharedHalfFov));
  shared.cameraOrbit = '0deg 90deg ' + sharedRadius + 'm';
  shared.jumpCameraToGoal();
}

function showScheme(index) {
  const returning = index === null;
  if (switching || selected === index) return;
  setHover(-1);
  const previous = selected;
  if (returning) {
    states[previous] = comparisonCamera;
    ({zoom, panX, panY} = comparisonFlat);
  } else {
    comparisonCamera = {...states[index]};
    comparisonFlat = {zoom, panX, panY};
    zoom = 1;
    panX = panY = 0;
  }
  selected = index;
  document.body.toggleAttribute('data-detail', !returning);
  compareTitle.hidden = !returning;
  shared.hidden = !returning;
  shortcuts.hidden = !returning;
  modelPair.hidden = returning;
  back.hidden = returning;
  scene.setAttribute('aria-label', returning ? '包装方案 3D 对比' : names[index] + ' 3D 展示');
  flat.setAttribute('aria-label', (returning ? '各方案' : names[index]) +
    '的彩色刀版。拖动平移，滚轮或双指缩放，Home 复位。');
  help.textContent = returning ? comparisonHelp : '拖动旋转，滚轮或双指缩放';
  for (const i of all) {
    const hidden = !returning && i !== index;
    viewers[i].hidden = images[i].hidden = hidden;
  }
  paintFlat();
  updateStatus();
  if (returning) {
    setView('model');
    paintSharedModel(previous);
    fitShared();
    scene.focus({preventScroll: true});
  } else {
    const detail = viewers[index];
    if (!detail.hasAttribute('src')) detail.setAttribute('src', detail.dataset.src);
    paintCamera(index);
    scene.focus({preventScroll: true});
  }
}

back.addEventListener('click', () => showScheme(null));
for (const shortcut of shortcuts.children) {
  shortcut.addEventListener('click', () => {
    if (sharedReady) showScheme(Number(shortcut.dataset.model));
  });
}

function setStatus(message) {
  status.textContent = message;
  status.hidden = !message;
}
const timeout = setTimeout(() => {
  if (!sharedReady) setStatus('模型加载超时，请刷新重试。');
}, 45000);
function updateStatus() {
  if (selected === null) {
    setStatus(sharedFailed ? '模型未能加载，请刷新重试。' : sharedReady ? '' : '正在加载包装模型…');
  } else {
    setStatus(failed.has(selected) ? names[selected] + '模型未能加载，请刷新重试。' :
      ready.has(selected) ? '' : '正在加载包装模型…');
  }
}

shared.addEventListener('load', () => {
  sharedReady = true;
  sharedFailed = false;
  shared.dataset.loaded = 'true';
  modelButton.disabled = false;
  clearTimeout(timeout);
  all.forEach(paintSharedModel);
  fitShared();
  updateStatus();
});
shared.addEventListener('error', () => {
  sharedFailed = true;
  sharedReady = false;
  clearTimeout(timeout);
  updateStatus();
});
new ResizeObserver(fitShared).observe(shared);

viewers.forEach((viewer, i) => {
  viewer.addEventListener('load', () => {
    ready.add(i);
    failed.delete(i);
    viewer.dataset.loaded = 'true';
    modelButton.disabled = false;
    paintCamera(i);
    updateStatus();
  });
  viewer.addEventListener('error', () => {
    ready.delete(i);
    failed.add(i);
    updateStatus();
  });
});
async function loadArtwork(i) {
  const image = images[i];
  if (!image.hasAttribute('src')) image.src = image.dataset.src;
  try {
    await image.decode();
  } catch (error) {
    image.removeAttribute('src');
    throw error;
  }
}

function loadFoldAssets() {
  foldAssets ??= Promise.all([
    import('./fold.js?v=' + revision),
    ...settings.schemes.map(async scheme => {
      if (!scheme.fold_config) return null;
      const name = scheme.fold_config;
      const response = await fetch(new URL(name + '?v=' + revision, import.meta.url));
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    }),
  ]).catch(error => {
    foldAssets = undefined;
    console.warn('折叠动画不可用，改为直接切换。', error);
    return null;
  });
  return foldAssets;
}

function paintCamera(i) {
  if (selected === null) {
    paintSharedModel(i);
    return;
  }
  if (i !== selected || !ready.has(i)) return;
  const {theta, phi, fov} = states[i];
  const viewer = viewers[i];
  viewer.cameraOrbit = theta + 'rad ' + phi + 'rad 108%';
  viewer.fieldOfView = fov + 'deg';
  viewer.jumpCameraToGoal();
}

function modelAt(x, y) {
  if (selected !== null) return selected;
  if (!sharedReady) return -1;
  const box = shared.getBoundingClientRect();
  if (x < box.left || x > box.right || y < box.top || y > box.bottom) return -1;
  return shared.positionAndNormalFromPoint(x, y)?.modelIndex ?? -1;
}

function targetsAt(x, y) {
  const hit = modelAt(x, y);
  return hit < 0 ? visibleModels() : [hit];
}

scene.addEventListener('pointermove', event => {
  if (event.pointerType !== 'mouse' || switching || selected !== null ||
      scene.classList.contains('is-dragging')) return;
  setHover(modelAt(event.clientX, event.clientY));
});
scene.addEventListener('pointerleave', () => setHover(-1));

function orbit(targets, dx, dy) {
  if (!dx && !dy) return;
  const reference = targets.length === 1 ? targets[0] : lastRotated;
  const start = states[reference];
  const theta = start.theta - dx * .011;
  const phi = Math.max(Math.PI / 90, Math.min(Math.PI * 89 / 90, start.phi - dy * .011));
  for (const i of targets) {
    states[i].theta = theta;
    states[i].phi = phi;
    paintCamera(i);
  }
  if (selected === null && targets.length === 1) lastRotated = reference;
}

function zoomModels(targets, factor) {
  if (selected === null) {
    sharedScale = Math.max(.65, Math.min(1.22, sharedScale / factor));
    animateSharedScale();
    return;
  }
  for (const i of targets) {
    states[i].fov = Math.max(17, Math.min(45, states[i].fov * factor));
    paintCamera(i);
  }
}

function paintFlat() {
  pair.style.transform = 'translate(' + panX + 'px, ' + panY + 'px) scale(' + zoom + ')';
}

function zoomFlat(factor, clientX, clientY) {
  const bounds = flat.getBoundingClientRect();
  const centerX = bounds.left + bounds.width / 2;
  const centerY = bounds.top + pair.offsetTop + pair.offsetHeight / 2;
  const x = (clientX ?? centerX) - centerX;
  const y = (clientY ?? centerY) - centerY;
  const next = Math.max(.45, Math.min(6, zoom * factor));
  panX = x + (panX - x) * next / zoom;
  panY = y + (panY - y) * next / zoom;
  zoom = next;
}

function pointerFrame(pointers) {
  const [first, second] = pointers.values();
  if (!second) return {...first, distance: 0};
  return {
    x: (first.x + second.x) / 2,
    y: (first.y + second.y) / 2,
    distance: Math.hypot(first.x - second.x, first.y - second.y),
  };
}

function bindDrag(surface, onStart, onMove, onTap) {
  const pointers = new Map();
  let gesture;
  let input;
  let origin;
  let dragging;
  surface.addEventListener('pointerdown', event => {
    if (switching || event.button !== 0 || pointers.size >= 2 ||
        (pointers.size && (input !== 'touch' || event.pointerType !== 'touch'))) return;
    if (!pointers.size) {
      gesture = onStart(event);
      input = event.pointerType;
      origin = {x:event.clientX, y:event.clientY};
      dragging = !onTap;
    } else {
      dragging = true;
    }
    surface.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
    surface.classList.add('is-dragging');
    event.preventDefault();
  });
  surface.addEventListener('pointermove', event => {
    if (!pointers.has(event.pointerId) || switching) return;
    let before = pointerFrame(pointers);
    pointers.set(event.pointerId, {x:event.clientX, y:event.clientY});
    if (!dragging) {
      if (Math.hypot(event.clientX - origin.x, event.clientY - origin.y) < 5) return;
      dragging = true;
      before = {...origin, distance: 0};
    }
    onMove(gesture, before, pointerFrame(pointers));
  });
  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    surface.addEventListener(type, event => {
      if (!pointers.delete(event.pointerId)) return;
      surface.classList.toggle('is-dragging', pointers.size > 0);
      if (type === 'pointerup' && !pointers.size && !dragging &&
          Math.hypot(event.clientX - origin.x, event.clientY - origin.y) < 5) {
        onTap?.(gesture, event);
      }
    });
  }
}

bindDrag(scene, event => {
  const targets = targetsAt(event.clientX, event.clientY);
  scene.focus({preventScroll: true});
  return targets;
}, (targets, before, after) => {
  setHover(-1);
  if (before.distance > 1 && after.distance > 1) zoomModels(targets, before.distance / after.distance);
  else orbit(targets, after.x - before.x, after.y - before.y);
}, (targets, event) => {
  if (selected === null && targets.length === 1 &&
      modelAt(event.clientX, event.clientY) === targets[0]) showScheme(targets[0]);
});
bindDrag(flat, () => flat.focus({preventScroll: true}), (_, before, after) => {
  if (before.distance > 1 && after.distance > 1) {
    zoomFlat(after.distance / before.distance, before.x, before.y);
  }
  panX += after.x - before.x;
  panY += after.y - before.y;
  paintFlat();
});

function wheelAmount(event) {
  return event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 120 : 1);
}

scene.addEventListener('wheel', event => {
  if (switching) return;
  event.preventDefault();
  zoomModels(targetsAt(event.clientX, event.clientY), Math.exp(wheelAmount(event) * .0016));
}, {passive: false});
flat.addEventListener('wheel', event => {
  if (switching) return;
  event.preventDefault();
  zoomFlat(Math.exp(-wheelAmount(event) * .0017), event.clientX, event.clientY);
  paintFlat();
}, {passive: false});

scene.addEventListener('keydown', event => {
  if (switching) return;
  if (event.target.closest('.scheme-shortcuts')) return;
  const targets = visibleModels();
  switch (event.key) {
    case 'ArrowLeft': orbit(targets, -17, 0); break;
    case 'ArrowRight': orbit(targets, 17, 0); break;
    case 'ArrowUp': orbit(targets, 0, -17); break;
    case 'ArrowDown': orbit(targets, 0, 17); break;
    case '+':
    case '=': zoomModels(targets, .87); break;
    case '-': zoomModels(targets, 1.15); break;
    case 'Home':
      if (selected === null) {
        sharedScale = 1;
        animateSharedScale();
      }
      visibleModels().forEach(index => {
        states[index] = {...initial};
        paintCamera(index);
      });
      break;
    default: return;
  }
  event.preventDefault();
});
flat.addEventListener('keydown', event => {
  if (switching) return;
  switch (event.key) {
    case 'ArrowUp':
    case '+':
    case '=': zoomFlat(1.15); break;
    case 'ArrowDown':
    case '-': zoomFlat(.87); break;
    case 'Home': zoom = 1; panX = 0; panY = 0; break;
    default: return;
  }
  event.preventDefault();
  paintFlat();
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

function closedFrame(viewer) {
  const bounds = viewer.getBoundingClientRect();
  const {radius, theta, phi} = viewer.getCameraOrbit();
  const field = viewer.getFieldOfView() * Math.PI / 180;
  const perspective = viewer.clientHeight / (2 * Math.tan(field / 2));
  const turn = -theta * 180 / Math.PI;
  return {
    pixelsPerUnit: perspective / radius,
    perspective,
    offsetX: bounds.left + bounds.width / 2 - window.innerWidth / 2,
    offsetY: bounds.top + bounds.height / 2 - window.innerHeight / 2,
    modelHeight: viewer.getDimensions().y,
    tilt: phi * 180 / Math.PI - 90,
    turn: ((turn + 180) % 360 + 360) % 360 - 180,
  };
}

function closedSharedFrame(i) {
  const bounds = shared.getBoundingClientRect();
  const {theta, phi} = states[i];
  const perspective = shared.clientHeight / (2 * Math.tan(sharedHalfFov));
  const pixelsPerUnit = perspective / sharedRadius;
  const turn = -theta * 180 / Math.PI;
  return {
    pixelsPerUnit,
    perspective,
    offsetX: bounds.left + bounds.width / 2 - window.innerWidth / 2 + centers[i] * pixelsPerUnit,
    offsetY: bounds.top + bounds.height / 2 - window.innerHeight / 2,
    modelHeight: boxHeight * sharedScale,
    tilt: phi * 180 / Math.PI - 90,
    turn: ((turn + 180) % 360 + 360) % 360 - 180,
  };
}

function openFrames(indices) {
  const hidden = flat.hidden;
  flat.hidden = false;
  const frames = indices.map(i => {
    const image = images[i];
    const bounds = image.getBoundingClientRect();
    return {
      width: image.offsetWidth,
      zoom,
      panX: bounds.left + bounds.width / 2 - window.innerWidth / 2,
      panY: bounds.top + bounds.height / 2 - window.innerHeight / 2,
    };
  });
  flat.hidden = hidden;
  return frames;
}

function setView(next) {
  view = next;
  document.body.dataset.view = view;
  const showFlat = next === 'flat';
  flat.hidden = !showFlat;
  scene.inert = showFlat;
  flatButton.setAttribute('aria-pressed', String(showFlat));
  modelButton.setAttribute('aria-pressed', String(!showFlat));
  modelButton.disabled = !showFlat && !sharedReady && selected === null;
}

async function switchView(next) {
  if (next === view || switching) return;
  switching = true;
  setHover(-1);
  const indices = visibleModels();
  const toFlat = next === 'flat';
  try {
    if (toFlat) {
      flatButton.setAttribute('aria-busy', 'true');
      if (indices.some(i => !images[i].complete || !images[i].naturalWidth)) {
        setStatus('正在加载展开图…');
      }
      await Promise.all(indices.map(loadArtwork));
    }

    const modelReady = selected === null ? sharedReady : ready.has(selected);
    // Touch browsers switch views without compositing 26 textured CSS panels over WebGL.
    const animateFold = modelReady && desktopPointer.matches && !reducedMotion.matches;
    const foldFilesAvailable = indices.every(i => settings.schemes[i].fold_config);
    const assets = animateFold && foldFilesAvailable ? await loadFoldAssets() : null;
    if (assets) {
      const [{createFold}, ...configs] = assets;
      const frames = indices.map(i => selected === null ? closedSharedFrame(i) : closedFrame(viewers[i]));
      const open = openFrames(indices);
      surfaces.forEach((surface, i) => { surface.hidden = !indices.includes(i); });
      const renderers = indices.map((i, j) => {
        const surface = surfaces[i];
        surface.style.perspective = frames[j].perspective + 'px';
        return createFold(surface, configs[i], images[i].src);
      });
      const render = progress => renderers.forEach((draw, j) => draw(progress, frames[j], open[j]));
      render(toFlat ? 0 : 1);
      flat.hidden = true;
      stage.hidden = false;
      document.body.dataset.view = 'folding';
      await animate(1050, progress => render(toFlat ? progress : 1 - progress));
    }
    setView(next);
    if (toFlat) setStatus('');
    else updateStatus();
  } catch (error) {
    setView(view);
    setStatus('展示切换失败，请重试。');
    console.warn(error);
  } finally {
    stage.hidden = true;
    surfaces.forEach(surface => surface.replaceChildren());
    flatButton.removeAttribute('aria-busy');
    switching = false;
  }
}

flatButton.addEventListener('click', () => void switchView('flat'));
modelButton.addEventListener('click', () => void switchView('model'));

function setClean(value) {
  setHover(-1);
  clean = value;
  document.body.toggleAttribute('data-clean', clean);
  fullscreen.setAttribute('aria-pressed', String(clean));
  const label = clean ? '退出全屏' : '全屏展示';
  fullscreen.setAttribute('aria-label', label);
  fullscreen.title = label;
}
fullscreen.addEventListener('click', async () => {
  if (switching) return;
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

import('./vendor/model-viewer.min.js?v=' + revision).catch(() => {
  clearTimeout(timeout);
  setStatus('三维查看器未能加载，请刷新重试。');
});




