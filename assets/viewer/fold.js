function makePanel(parent, bounds, origin, outline) {
  const [left, top, right, bottom] = bounds;
  const node = document.createElement('div');
  node.className = 'fold-panel';
  for (const [name, value] of Object.entries({
    'panel-x': left - origin[0], 'panel-y': top - origin[1],
    'panel-width': right - left, 'panel-height': bottom - top,
    'print-x': -left, 'print-y': -top,
  })) node.style.setProperty('--' + name, value + 'px');
  if (outline) node.style.setProperty('--outline', 'polygon(' + outline + ')');
  const print = document.createElement('div');
  const inside = document.createElement('div');
  print.className = 'fold-print';
  inside.className = 'fold-inside';
  node.append(print, inside);
  parent.append(node);
  return node;
}

export function createFold(stage, config, imageUrl) {
  const [artworkWidth, artworkHeight] = config.artwork;
  const [frontLeft, frontTop, frontRight, frontBottom] = config.panels[0].bounds;
  const root = document.createElement('div');
  root.className = 'fold-root';
  root.style.setProperty('--artwork-size', `${artworkWidth}px ${artworkHeight}px`);
  root.style.setProperty('--fold-artwork', `url("${imageUrl}")`);
  stage.append(root);
  const panels = [];
  for (const definition of config.panels) {
    const { bounds, parent, hinge, axis, angle, outline, timing } = definition;
    const parentPanel = panels[parent];
    const node = makePanel(parentPanel?.node ?? root, bounds, parentPanel?.bounds ?? [frontLeft, frontTop], outline);
    if (hinge) node.style.transformOrigin = `${hinge[0] - bounds[0]}px ${hinge[1] - bounds[1]}px`;
    if (outline) node.classList.add('flap');
    panels.push({ node, bounds, axis, angle, timing: timing ?? [0, 1] });
  }

  return (progress, closed, flat) => {
    for (const { node, axis, angle, timing: [start, end] } of panels.slice(1)) {
      const unfolded = ease(Math.min(1, Math.max(0, (progress - start) / (end - start))));
      node.style.transform = `rotate${axis}(${angle * (1 - unfolded)}deg)`;
    }

    const amount = ease(progress);
    const frame = (start, end) => start + (end - start) * amount;
    const frontHeight = frontBottom - frontTop;
    const scale = frame(closed.pixelsPerUnit * closed.modelHeight / frontHeight, flat.width / artworkWidth * flat.zoom);
    const x = frame((frontRight - frontLeft) / 2, artworkWidth / 2 - frontLeft);
    const y = frame(frontHeight / 2, artworkHeight / 2 - frontTop);
    root.style.transform = `translate(${frame(closed.offsetX, flat.panX)}px, ${frame(closed.offsetY, flat.panY)}px)
      rotateX(${frame(closed.tilt, 0)}deg)
      rotateY(${frame(closed.turn, 0)}deg) scale3d(${scale}, ${scale}, ${scale}) translate(${-x}px, ${-y}px)`;
  };
}

function ease(t) {
  return t * t * (3 - 2 * t);
}
