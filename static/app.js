/* ── DRIP STORE — app.js ── */

// ── TOKEN & USER ──────────────────────────────────────
const getToken = () => localStorage.getItem('drip_token');
const getUser  = () => JSON.parse(localStorage.getItem('drip_user') || 'null');
const setSession = (token, user) => { localStorage.setItem('drip_token', token); localStorage.setItem('drip_user', JSON.stringify(user)); };
const clearSession = () => { localStorage.removeItem('drip_token'); localStorage.removeItem('drip_user'); };
const isLoggedIn = () => !!getToken();

// ── API HELPER ────────────────────────────────────────
async function api(method, path, body) {
  const headers = { 'Content-Type': 'application/json' };
  if (getToken()) headers['Authorization'] = 'Bearer ' + getToken();
  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch('/api' + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Something went wrong');
  return data;
}

// ── TOAST ─────────────────────────────────────────────
function showToast(msg, type) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.style.borderLeft = '3px solid ' + (type === 'success' ? '#2e7d32' : type === 'error' ? '#c62828' : '#b8860b');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 3000);
}

// ── CURRENCY ──────────────────────────────────────────
const rupee = n => '₹' + Number(n).toLocaleString('en-IN');

// ── CART BADGE ────────────────────────────────────────
async function refreshCart() {
  if (!isLoggedIn()) return;
  try {
    const data = await api('GET', '/cart');
    const badge = document.getElementById('cartBadge');
    if (badge) {
      badge.textContent = data.item_count || '';
      badge.style.display = data.item_count > 0 ? 'flex' : 'none';
    }
  } catch(e) {}
}

// ── NAV UPDATE ────────────────────────────────────────
function updateNav() {
  const user = getUser();
  const btn = document.getElementById('navAccountBtn');
  if (btn && user) {
    btn.textContent = user.first_name;
    btn.onclick = () => location.href = '/account.html';
  }
  const adminBtnId = 'navAdminBtn';
  const existingAdminBtn = document.getElementById(adminBtnId);
  if (user && user.is_admin) {
    if (!existingAdminBtn) {
      const adminBtn = document.createElement('button');
      adminBtn.id = adminBtnId;
      adminBtn.className = 'btn-outline';
      adminBtn.textContent = 'Admin';
      adminBtn.style.marginRight = '0.75rem';
      adminBtn.onclick = () => location.href = '/admin.html';
      const navRight = document.querySelector('.nav-right');
      if (navRight) navRight.insertBefore(adminBtn, navRight.firstChild);
    }
  } else if (existingAdminBtn) {
    existingAdminBtn.remove();
  }}

// ── PRODUCT CARD RENDERER ─────────────────────────────
function renderCard(p) {
  const price = rupee(p.price);
  const orig  = p.original_price ? `<span class="orig">${rupee(p.original_price)}</span>` : '';
  const badge = p.badge ? `<span class="prod-badge badge-${p.badge}">${p.badge}</span>` : '';
  const stars = '★'.repeat(Math.round(p.rating)) + '☆'.repeat(5 - Math.round(p.rating));
  const emojis = {'Tops':'👕','Hoodies':'🧥','Bottoms':'👖','Outerwear':'🧥','Accessories':'🎒','Footwear':'👟'};
  const emoji = emojis[p.category] || '👕';
  return `
    <div class="prod-card" onclick="location.href='/product.html?slug=${p.slug}'">
      <div class="prod-img">
        ${badge}
        <button class="wish-btn" id="wish-${p.id}" onclick="event.stopPropagation();toggleWish(${p.id},this)">♡</button>
        <div class="prod-emoji">${emoji}</div>
        <div class="prod-overlay">
          <button class="add-btn" onclick="event.stopPropagation();quickAdd(${p.id})">Add to Cart</button>
        </div>
      </div>
      <div class="prod-info">
        <p class="prod-cat">${p.category}</p>
        <p class="prod-name">${p.name}</p>
        <div class="prod-meta">
          <span class="prod-price">${price}${orig}</span>
          <span class="prod-rating"><span class="star">${stars.slice(0,1)}</span> ${p.rating}</span>
        </div>
      </div>
    </div>`;
}

// ── QUICK ADD TO CART ─────────────────────────────────
async function quickAdd(productId) {
  if (!isLoggedIn()) { showToast('Please login to add to cart'); setTimeout(() => location.href='/login.html', 1200); return; }
  try {
    await api('POST', '/cart/add', { product_id: productId, quantity: 1 });
    await refreshCart();
    showToast('Added to cart!', 'success');
  } catch(e) { showToast(e.message, 'error'); }
}

// ── TOGGLE WISHLIST ───────────────────────────────────
async function toggleWish(productId, btn) {
  if (!isLoggedIn()) { showToast('Please login to use wishlist'); return; }
  const wished = btn.textContent === '♥';
  try {
    if (wished) {
      await api('DELETE', '/wishlist/' + productId);
      btn.textContent = '♡'; btn.classList.remove('active');
      showToast('Removed from wishlist');
    } else {
      await api('POST', '/wishlist/' + productId, {});
      btn.textContent = '♥'; btn.classList.add('active');
      showToast('Added to wishlist!', 'success');
    }
  } catch(e) { showToast(e.message, 'error'); }
}

// ── AUTO INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateNav();
  refreshCart();
});
