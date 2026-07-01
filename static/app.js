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

// ── WISHLIST CACHE & SYNC ─────────────────────────────
window.wishlistIds = [];
async function initWishlist() {
  if (!isLoggedIn()) return;
  try {
    const items = await api('GET', '/wishlist');
    window.wishlistIds = items.map(item => item.product_id);
    document.querySelectorAll('.wish-btn').forEach(btn => {
      const pid = parseInt(btn.id.replace('wish-', ''));
      if (window.wishlistIds.includes(pid)) {
        btn.textContent = '♥';
        btn.classList.add('active');
      }
    });
  } catch(e) {}
}

// ── PRODUCT CARD RENDERER ─────────────────────────────
function renderCard(p) {
  const price = rupee(p.price);
  const orig  = p.original_price ? `<span class="orig">${rupee(p.original_price)}</span>` : '';
  const badge = p.badge ? `<span class="prod-badge badge-${p.badge}">${p.badge}</span>` : '';
  const stars = '★'.repeat(Math.round(p.rating)) + '☆'.repeat(5 - Math.round(p.rating));
  const emojis = {'Tops':'👕','Hoodies':'🧥','Bottoms':'👖','Outerwear':'🧥','Accessories':'🎒','Footwear':'👟'};
  const emoji = emojis[p.category] || '👕';
  const isWished = window.wishlistIds.includes(p.id);
  const heartIcon = isWished ? '♥' : '♡';
  const activeClass = isWished ? ' active' : '';
  const imgContent = p.image_url 
    ? `<img src="${p.image_url}" class="prod-img-file" style="width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0;transition:transform 0.4s"/>` 
    : `<div class="prod-emoji">${emoji}</div>`;
    
  return `
    <div class="prod-card" onclick="location.href='/product.html?slug=${p.slug}'">
      <div class="prod-img">
        ${badge}
        <button class="wish-btn${activeClass}" id="wish-${p.id}" onclick="event.stopPropagation();toggleWish(${p.id},this)">${heartIcon}</button>
        ${imgContent}
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
    toggleCartDrawer(true);
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
      window.wishlistIds = window.wishlistIds.filter(id => id !== productId);
      showToast('Removed from wishlist');
    } else {
      await api('POST', '/wishlist/' + productId, {});
      btn.textContent = '♥'; btn.classList.add('active');
      if (!window.wishlistIds.includes(productId)) window.wishlistIds.push(productId);
      showToast('Added to wishlist!', 'success');
    }
  } catch(e) { showToast(e.message, 'error'); }
}

// ── INJECT & MANAGE CART DRAWER ───────────────────────
function injectCartDrawer() {
  const container = document.createElement('div');
  container.innerHTML = `
  <div id="cartDrawer" class="cart-drawer" style="position:fixed;top:0;right:-420px;width:100%;max-width:400px;height:100%;background:#fff;box-shadow:-10px 0 30px rgba(0,0,0,0.1);z-index:1001;transition:right 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);display:flex;flex-direction:column">
    <div class="drawer-header" style="padding:1.5rem;border-bottom:1px solid #eee;display:flex;justify-content:space-between;align-items:center">
      <h3 style="font-family:'Playfair Display',serif;margin:0;font-size:1.4rem">Shopping Cart</h3>
      <button onclick="toggleCartDrawer(false)" style="background:none;border:none;font-size:1.8rem;cursor:pointer;color:#999;outline:none">&times;</button>
    </div>
    <div id="drawerItems" style="flex:1;overflow-y:auto;padding:1.5rem;display:flex;flex-direction:column;gap:1.25rem">
      <p style="color:#aaa;font-style:italic;text-align:center;padding:2rem 0">Loading items...</p>
    </div>
    <div class="drawer-footer" style="padding:1.5rem;border-top:1px solid #eee;background:#fafafa">
      <div style="display:flex;justify-content:space-between;margin-bottom:1rem;font-weight:600">
        <span>Subtotal:</span>
        <span id="drawerSubtotal" style="color:var(--gold)">₹0</span>
      </div>
      <button class="btn-gold btn-full btn-lg" onclick="location.href='/checkout.html'" style="display:block;text-align:center">Checkout</button>
    </div>
  </div>
  <div id="drawerOverlay" onclick="toggleCartDrawer(false)" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.4);z-index:1000;display:none;opacity:0;transition:opacity 0.3s ease;backdrop-filter:blur(3px)"></div>
  `;
  document.body.appendChild(container);
}

function setupCartIconInterceptor() {
  const cartIcon = document.querySelector('.cart-icon');
  if (cartIcon) {
    cartIcon.addEventListener('click', (e) => {
      if (location.pathname.endsWith('/cart.html')) return;
      e.preventDefault();
      toggleCartDrawer(true);
    });
  }
}

function toggleCartDrawer(open) {
  const drawer = document.getElementById('cartDrawer');
  const overlay = document.getElementById('drawerOverlay');
  if (!drawer || !overlay) return;
  if (open) {
    loadDrawerCart();
    drawer.style.right = '0';
    overlay.style.display = 'block';
    setTimeout(() => overlay.style.opacity = '1', 50);
  } else {
    drawer.style.right = '-420px';
    overlay.style.opacity = '0';
    setTimeout(() => overlay.style.display = 'none', 300);
  }
}

async function loadDrawerCart() {
  const container = document.getElementById('drawerItems');
  const subtotalEl = document.getElementById('drawerSubtotal');
  if (!isLoggedIn()) {
    container.innerHTML = '<p style="color:#aaa;text-align:center;padding:2rem 0">Please <a href="/login.html" style="color:var(--gold);text-decoration:underline">login</a> to view your cart.</p>';
    subtotalEl.textContent = '₹0';
    return;
  }
  
  try {
    const data = await api('GET', '/cart');
    subtotalEl.textContent = rupee(data.subtotal);
    
    if (!data.items.length) {
      container.innerHTML = '<p style="color:#aaa;text-align:center;padding:2rem 0">Your cart is empty.</p>';
      return;
    }
    
    container.innerHTML = data.items.map(item => {
      const p = item.product;
      const sizeStr = item.size ? `<span style="font-size:0.75rem;color:#888;background:#f5f0ea;padding:0.15rem 0.35rem;border-radius:4px;margin-right:0.3rem">Size: ${item.size}</span>` : '';
      const colorStr = item.color ? `<span style="font-size:0.75rem;color:#888;background:#f5f0ea;padding:0.15rem 0.35rem;border-radius:4px">Color: ${item.color}</span>` : '';
      const imgMarkup = p.image_url 
        ? `<img src="${p.image_url}" style="width:50px;height:60px;object-fit:cover;border-radius:4px"/>`
        : `<div style="width:50px;height:60px;background:#f5f0ea;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:1.8rem">👕</div>`;
        
      return `
      <div style="display:flex;gap:1rem;align-items:start;padding-bottom:1rem;border-bottom:1px solid #f2ede4">
        ${imgMarkup}
        <div style="flex:1">
          <h4 style="font-size:0.85rem;font-weight:600;margin:0 0 0.25rem">${p.name}</h4>
          <div style="margin-bottom:0.5rem;display:flex;flex-wrap:wrap;gap:0.25rem">
            ${sizeStr}${colorStr}
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="display:flex;align-items:center;gap:0.4rem;border:1px solid #ddd;border-radius:4px;padding:0.15rem 0.3rem">
              <button onclick="updateDrawerQty('${item.id}', ${item.quantity - 1})" style="background:none;border:none;cursor:pointer;font-size:0.85rem;font-weight:600;width:15px">-</button>
              <span style="font-size:0.85rem;font-weight:600">${item.quantity}</span>
              <button onclick="updateDrawerQty('${item.id}', ${item.quantity + 1})" style="background:none;border:none;cursor:pointer;font-size:0.85rem;font-weight:600;width:15px">+</button>
            </div>
            <strong style="color:var(--gold);font-size:0.9rem">${rupee(p.price * item.quantity)}</strong>
          </div>
        </div>
        <button onclick="removeDrawerItem('${item.id}')" style="background:none;border:none;cursor:pointer;color:#999;font-size:1.1rem;outline:none">&times;</button>
      </div>
      `;
    }).join('');
  } catch(e) {
    container.innerHTML = '<p style="color:var(--red);text-align:center;padding:2rem 0">Failed to load cart items.</p>';
  }
}

async function updateDrawerQty(itemId, newQty) {
  if (newQty <= 0) return removeDrawerItem(itemId);
  try {
    await api('PUT', '/cart/' + itemId, { quantity: newQty });
    loadDrawerCart();
    await refreshCart();
  } catch(e) {
    showToast(e.message, 'error');
  }
}

async function removeDrawerItem(itemId) {
  try {
    await api('DELETE', '/cart/' + itemId);
    loadDrawerCart();
    await refreshCart();
    showToast('Item removed');
  } catch(e) {
    showToast(e.message, 'error');
  }
}

// ── AUTO INIT ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateNav();
  refreshCart();
  injectCartDrawer();
  setupCartIconInterceptor();
  initWishlist();
});
