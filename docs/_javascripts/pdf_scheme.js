document.addEventListener('DOMContentLoaded', function () {
  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[href*="_pdf.html"]');
    if (!a) return;
    var scheme = document.body.getAttribute('data-md-color-scheme') || 'default';
    var base = a.href.split('?')[0];
    a.href = base + '?scheme=' + scheme;
  });
});
