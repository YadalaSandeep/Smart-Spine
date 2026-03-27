/**
 * app.js
 * SPA Hash Router & Authentication
 */

const $ = id => document.getElementById(id);

// --- Auth State ---
let currentUser = null; // { name, email }

function loadUser() {
  try {
    const data = localStorage.getItem('spine_user');
    if (data) {
      currentUser = JSON.parse(data);
    }
  } catch (err) {
    console.error("[Auth] Failed to load user from localStorage", err);
    localStorage.removeItem('spine_user');
  }
}

function saveUser(user) {
  if (user) {
    localStorage.setItem('spine_user', JSON.stringify(user));
    currentUser = user;
  } else {
    localStorage.removeItem('spine_user');
    currentUser = null;
  }
  updateAuthUI();
}

function updateAuthUI() {
  if (currentUser) {
    $('userBadge').style.display = 'flex';
    $('userAvatar').textContent = currentUser.name.charAt(0).toUpperCase();
    $('userNamebadge').textContent = currentUser.name;
    
    $('authStatusMenu').innerHTML = `
      <div class="user-info text-sm text-secondary mb-2 px-2">Signed in as ${currentUser.name}</div>
      <a href="#profile" class="nav-btn bg-white/5"><span class="icon">👤</span> My Profile</a>
    `;
    
    // Populate profile inputs if they exist
    if ($('profName')) $('profName').value = currentUser.name;
    if ($('profEmail')) $('profEmail').value = currentUser.email;
    
  } else {
    $('userBadge').style.display = 'none';
    $('authStatusMenu').innerHTML = `
      <a href="#login" class="btn btn-primary w-full mb-2 text-center" style="display:block;">Log In</a>
      <a href="#signup" class="nav-auth text-center">Create Account</a>
    `;
  }
}

// --- Routing ---
const routes = {
  'home': { title: 'SmartSpine AI', public: true },
  'services': { title: 'AI Services', public: true },
  'monitor': { title: 'Live Posture Monitor', public: true },
  'analytics': { title: 'Analytics Dashboard', public: true },
  'exercises': { title: 'Correction Exercises', public: true },
  'resources': { title: 'Health Resources', public: true },

  'profile': { title: 'My Profile', public: false },
  'login': { title: 'Log In', public: true },
  'signup': { title: 'Sign Up', public: true },
};

function navigate() {
  let hash = window.location.hash.substring(1) || 'home';
  
  // Guard protected routes
  if (routes[hash] && !routes[hash].public && !currentUser) {
    window.location.hash = 'login';
    return;
  }
  
  // Default to home if invalid route
  if (!routes[hash]) hash = 'home';
  
  // Update Topbar Title
  $('topbarTitle').textContent = routes[hash].title;

  // Toggle sections
  document.querySelectorAll('.spa-view').forEach(el => {
    el.classList.remove('active');
  });
  const view = $(`view-${hash}`);
  if (view) view.classList.add('active');

  // Highlight sidebar
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.classList.remove('active');
    if (btn.dataset.view === hash) {
      btn.classList.add('active');
    }
  });

  // Execute view-specific logic
  if (hash === 'analytics' || hash === 'exercises') {
    if (window.loadDashboardData) window.loadDashboardData();
  }
}

// --- Boot ---
document.addEventListener('DOMContentLoaded', () => {
  // Clear any legacy e-commerce data as per requirements
  localStorage.removeItem('cart_items');
  localStorage.removeItem('order_history');
  localStorage.removeItem('cart_total');

  loadUser();
  updateAuthUI();
  
  // Forms
  if ($('loginForm')) {
    $('loginForm').addEventListener('submit', (e) => {
      e.preventDefault();
      saveUser({ name: 'Test User', email: $('logEmail').value });
      window.location.hash = 'home';
    });
  }
  if ($('signupForm')) {
    $('signupForm').addEventListener('submit', (e) => {
      e.preventDefault();
      saveUser({ name: $('signName').value, email: $('signEmail').value });
      window.location.hash = 'home';
    });
  }
  if ($('btnLogout')) {
    $('btnLogout').addEventListener('click', () => {
      saveUser(null);
      window.location.hash = 'home';
    });
  }

  // Listen for hash changes
  window.addEventListener('hashchange', navigate);
  
  // Initial route
  navigate();
});
