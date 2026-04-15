/* UAE Heritage Archive — main.js */

document.addEventListener('DOMContentLoaded', () => {

  // ── Sticky Nav ────────────────────────────────────
  const nav = document.getElementById('nav');
  if (nav) {
    window.addEventListener('scroll', () => {
      nav.classList.toggle('nav--scrolled', window.scrollY > 40);
    }, { passive: true });
  }

  // ── Mobile Nav Toggle ─────────────────────────────
  const toggle = document.getElementById('navToggle');
  const links  = document.querySelector('.nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => {
      links.classList.toggle('nav-open');
    });
  }

  // ── AOS (Animate On Scroll) ───────────────────────
  const aosEls = document.querySelectorAll('[data-aos]');
  if (aosEls.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          const delay = parseInt(el.dataset.aosDelay || 0);
          setTimeout(() => el.classList.add('aos-visible'), delay);
          observer.unobserve(el);
        }
      });
    }, { threshold: 0.1 });

    aosEls.forEach(el => observer.observe(el));
  }

  // ── Auto-dismiss flashes ──────────────────────────
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.transition = 'opacity 0.5s';
      f.style.opacity = '0';
      setTimeout(() => f.remove(), 500);
    }, 4000);
  });

  // ── Form loading state ────────────────────────────
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type=submit]');
      if (btn && !btn.dataset.noLoading) {
        btn.disabled = true;
        const orig = btn.innerHTML;
        btn.innerHTML = '<span style="opacity:0.7">Processing...</span>';
        // Re-enable after 15s as fallback
        setTimeout(() => { btn.disabled = false; btn.innerHTML = orig; }, 15000);
      }
    });
  });

  // ── Story card hover depth ────────────────────────
  document.querySelectorAll('.story-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.zIndex = '10';
    });
    card.addEventListener('mouseleave', () => {
      card.style.zIndex = '';
    });
  });

  // ── Smooth category pill indicator ───────────────
  const catCards = document.querySelectorAll('.cat-card');
  catCards.forEach(card => {
    card.addEventListener('mouseenter', function() {
      this.style.borderLeft = '3px solid #C9A84C';
    });
    card.addEventListener('mouseleave', function() {
      this.style.borderLeft = '';
    });
  });

  // ── Archive search auto-submit ────────────────────
  const searchInput = document.querySelector('input[name="q"]');
  if (searchInput) {
    let searchTimer;
    searchInput.addEventListener('input', function() {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        this.form.submit();
      }, 600);
    });
  }

  // ── Image preview on file select ─────────────────
  const fileInput = document.querySelector('input[type="file"][name="image"]');
  if (fileInput) {
    fileInput.addEventListener('change', function() {
      const file = this.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = e => {
        let preview = document.getElementById('img-preview');
        if (!preview) {
          preview = document.createElement('div');
          preview.id = 'img-preview';
          preview.style.cssText = 'margin-top:0.7rem;';
          fileInput.parentNode.appendChild(preview);
        }
        preview.innerHTML = `<img src="${e.target.result}" style="max-height:120px;border-radius:4px;border:1px solid rgba(12,27,51,0.15);"/>`;
      };
      reader.readAsDataURL(file);
    });
  }

  // ── Keyboard shortcut: Esc to close chat ─────────
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      const panel = document.getElementById('chatPanel');
      const fab   = document.getElementById('chatFab');
      if (panel && panel.classList.contains('chat-panel--open')) {
        panel.classList.remove('chat-panel--open');
        if (fab) fab.style.display = '';
      }
    }
  });

  // ── Admin table: row click to story ──────────────
  document.querySelectorAll('.admin-table tbody tr').forEach(row => {
    const viewLink = row.querySelector('.action-btn--view');
    if (viewLink) {
      row.style.cursor = 'pointer';
      row.addEventListener('click', e => {
        if (!e.target.closest('button') && !e.target.closest('a') && !e.target.closest('form')) {
          viewLink.click();
        }
      });
    }
  });

  // ── Animate count-up for hero stats ──────────────
  const statNums = document.querySelectorAll('.hero-stat__num');
  statNums.forEach(el => {
    const target = parseInt(el.textContent);
    if (isNaN(target) || target < 2) return;
    el.textContent = '0';
    const duration = 1200;
    const start = performance.now();
    const animate = (now) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(eased * target);
      if (progress < 1) requestAnimationFrame(animate);
    };
    setTimeout(() => requestAnimationFrame(animate), 500);
  });

});
