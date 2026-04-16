/* Butler Button — comparison pages shared JS
   Nav bg on scroll, reveal observer, sticky CTA, FAQ (uses <details>). */
(function () {
  'use strict';
  var noMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── NAV bg on scroll ───────────────────────────── */
  var nav = document.getElementById('main-nav');
  if (nav) {
    window.addEventListener('scroll', function () {
      nav.classList.toggle('bg', window.scrollY > 60);
    }, { passive: true });
  }

  /* ── REVEAL on scroll ───────────────────────────── */
  if (!noMotion && 'IntersectionObserver' in window) {
    var revealObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          revealObs.unobserve(e.target);
        }
      });
    }, { rootMargin: '0px 0px -7% 0px', threshold: 0.08 });

    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      revealObs.observe(el);
    });
  } else {
    /* If reduced motion or no IO, just show everything immediately */
    document.querySelectorAll('[data-reveal]').forEach(function (el) {
      el.classList.add('visible');
    });
  }

  /* ── MOBILE STICKY CTA — show after hero CTA scrolls out ── */
  var stickyCta = document.getElementById('sticky-cta');
  var heroActions = document.querySelector('.hero-actions');
  if (stickyCta && heroActions && 'IntersectionObserver' in window) {
    var stickyObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        stickyCta.classList.toggle('visible', !e.isIntersecting);
      });
    }, { threshold: 0 });
    stickyObs.observe(heroActions);
  }

  /* ── FAQ — close siblings on open (single-open pattern) ── */
  var faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(function (item) {
    item.addEventListener('toggle', function () {
      if (item.open) {
        faqItems.forEach(function (other) {
          if (other !== item) other.open = false;
        });
      }
    });
  });
})();
