(function () {
  var chart = document.querySelector('[data-bar-chart="desempenho-vendas"]');
  if (!chart) return;
  var tooltip = chart.querySelector('.bar-chart__tooltip');
  var ttTotal = tooltip.querySelector('[data-tt-total]');
  var ttLabel = tooltip.querySelector('[data-tt-label]');
  var ttCount = tooltip.querySelector('[data-tt-count]');
  var bars = chart.querySelectorAll('.bar-chart__bar');

  function show(bar, x, y) {
    ttTotal.textContent = bar.dataset.total;
    ttLabel.textContent = bar.dataset.label;
    ttCount.textContent = bar.dataset.count;
    tooltip.style.left = x + 'px';
    tooltip.style.top = y + 'px';
    tooltip.setAttribute('data-visible', 'true');
  }
  function hide() { tooltip.removeAttribute('data-visible'); }

  bars.forEach(function (bar) {
    bar.style.height = bar.dataset.pct + '%';
    bar.addEventListener('pointermove', function (e) { show(bar, e.clientX, e.clientY - 12); });
    bar.addEventListener('pointerenter', function (e) { show(bar, e.clientX, e.clientY - 12); });
    bar.addEventListener('pointerleave', hide);
    bar.addEventListener('focus', function () {
      var rect = bar.getBoundingClientRect();
      show(bar, rect.left + rect.width / 2, rect.top - 8);
    });
    bar.addEventListener('blur', hide);
  });
})();
