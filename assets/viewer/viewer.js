(() => {
  const viewer = document.querySelector('model-viewer');
  const status = document.getElementById('load-status');
  let finished = false;
  const timeout = setTimeout(() => {
    if (!finished) fail('模型加载超时，请刷新重试。');
  }, 45000);
  function fail(message) {
    if (finished) return;
    clearTimeout(timeout);
    status.hidden = false;
    status.textContent = message;
  }
  viewer.addEventListener('load', () => {
    finished = true;
    clearTimeout(timeout);
    status.hidden = true;
    viewer.dataset.loaded = 'true';
  });
  viewer.addEventListener('error', () => fail('模型未能加载，请刷新重试。'));
  viewer.addEventListener('keydown', event => {
    if (event.key === 'Home') {
      event.preventDefault();
      viewer.cameraOrbit = viewer.dataset.initialOrbit;
      viewer.cameraTarget = 'auto auto auto';
      if (matchMedia('(prefers-reduced-motion: reduce)').matches) viewer.jumpCameraToGoal();
    }
  });
  import('./vendor/model-viewer.min.js').catch(() => fail('三维查看器未能加载，请刷新重试。'));
})();
