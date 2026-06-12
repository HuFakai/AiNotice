/**
 * 爱通知 · 统一布局外壳 (layout.js)
 * 注入侧边栏 + 顶栏、处理认证守卫、主题切换、移动端抽屉与登出。
 * 取代旧 app.js 的布局/认证职责。
 *
 * 页面用法：
 *   <body data-page="dashboard" data-title="控制台">
 *     ...页面内容（无需手写侧边栏/顶栏）...
 *     <script>Layout.mount();</script>
 *   layout.js 会移除旧的 .navbar、把现有内容包入外壳并注入侧边栏+顶栏。
 */
(function () {
  const NAV = [
    { key: 'dashboard',  label: '控制台',   icon: 'fa-gauge-high',      href: '/dashboard' },
    { key: 'api-keys',   label: 'API密钥',  icon: 'fa-key',             href: '/api-keys' },
    { key: 'devices',    label: '设备管理', icon: 'fa-tower-broadcast', href: '/devices' },
    { key: 'mi-accounts',label: '小米账户', icon: 'fa-user-gear',       href: '/mi-accounts' },
    { key: 'analytics',  label: 'API统计',  icon: 'fa-chart-line',      href: '/analytics' },
    { key: 'docs',       label: '开发文档', icon: 'fa-book',            href: '/docs-page' },
    { key: 'profile',    label: '个人资料', icon: 'fa-user',            href: '/profile' },
  ];

  const Layout = {
    mount(opts = {}) {
      const page = opts.page || document.body.dataset.page || '';
      const title = opts.title || document.body.dataset.title || '';

      // 1) 认证守卫（同步，先于渲染重定向）
      if (opts.requireAuth !== false && !this._hasToken()) {
        window.location.href = '/login';
        return;
      }

      this._restructure(page, title);
      this._bindEvents();
      this._fillUser();

      // 2) 异步校验令牌有效性
      if (opts.requireAuth !== false) this._verify();
    },

    _hasToken() { return !!localStorage.getItem('auth_token'); },

    /** 移除旧的重复顶部导航，把现有页面内容包入外壳，并注入侧边栏+顶栏 */
    _restructure(page, title) {
      // 移除各页复制粘贴的旧顶部导航
      document.querySelectorAll('.navbar').forEach(n => n.remove());

      // 将 body 现有子节点收集为页面内容
      const wrapper = document.createElement('div');
      wrapper.className = 'content-wrapper';
      while (document.body.firstChild) wrapper.appendChild(document.body.firstChild);

      const sidebar = this._buildSidebar(page);
      const backdrop = document.createElement('div');
      backdrop.className = 'sidebar-backdrop';
      backdrop.id = 'sidebarBackdrop';

      const main = document.createElement('div');
      main.className = 'app-main';
      main.appendChild(this._buildTopbar(title));
      main.appendChild(wrapper);

      document.body.appendChild(sidebar);
      document.body.appendChild(backdrop);
      document.body.appendChild(main);
    },

    _buildSidebar(page) {
      const links = NAV.map(n => `
        <a href="${n.href}" class="sidebar-link${n.key === page ? ' active' : ''}">
          <i class="fas ${n.icon}"></i><span>${n.label}</span>
        </a>`).join('');
      const aside = document.createElement('aside');
      aside.className = 'app-sidebar';
      aside.id = 'appSidebar';
      aside.innerHTML = `
        <a href="/dashboard" class="sidebar-brand">
          <span class="brand-logo"><i class="fas fa-bell"></i></span>
          <span>爱通知</span>
        </a>
        <nav class="sidebar-nav">
          <div class="sidebar-section-label">导航</div>
          ${links}
        </nav>
        <div class="sidebar-footer">
          <a href="#" class="sidebar-link" id="navLogout"><i class="fas fa-right-from-bracket"></i><span>退出登录</span></a>
        </div>`;
      return aside;
    },

    _buildTopbar(title) {
      const bar = document.createElement('header');
      bar.className = 'app-topbar';
      bar.innerHTML = `
        <button class="icon-btn menu-toggle" id="menuToggle" aria-label="菜单"><i class="fas fa-bars"></i></button>
        <div class="topbar-title">${title}</div>
        <div class="topbar-spacer"></div>
        <div class="topbar-actions">
          <button class="icon-btn" id="themeToggle" aria-label="切换主题"><i class="fas fa-moon"></i></button>
          <div class="topbar-user" id="userMenu">
            <span class="avatar" id="userAvatar">U</span>
            <span id="userDisplayName">加载中...</span>
            <i class="fas fa-chevron-down" style="font-size:11px;color:var(--text-3)"></i>
          </div>
        </div>`;
      return bar;
    },

    _bindEvents() {
      // 主题
      this._applyTheme(localStorage.getItem('theme') || 'light');
      const tt = document.getElementById('themeToggle');
      if (tt) tt.addEventListener('click', () => {
        const next = (localStorage.getItem('theme') || 'light') === 'light' ? 'dark' : 'light';
        this._applyTheme(next);
      });

      // 移动端抽屉
      const sidebar = document.getElementById('appSidebar');
      const backdrop = document.getElementById('sidebarBackdrop');
      const menu = document.getElementById('menuToggle');
      const close = () => { sidebar && sidebar.classList.remove('open'); backdrop && backdrop.classList.remove('show'); };
      if (menu) menu.addEventListener('click', () => { sidebar.classList.toggle('open'); backdrop.classList.toggle('show'); });
      if (backdrop) backdrop.addEventListener('click', close);

      // 用户菜单 → 跳转个人资料
      const um = document.getElementById('userMenu');
      if (um) um.addEventListener('click', () => { window.location.href = '/profile'; });

      // 登出
      const lo = document.getElementById('navLogout');
      if (lo) lo.addEventListener('click', (e) => { e.preventDefault(); this.logout(); });
    },

    _applyTheme(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('theme', theme);
      const icon = document.querySelector('#themeToggle i');
      if (icon) icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    },

    _fillUser() {
      const user = (window.apiClient && window.apiClient.getCurrentUser()) || null;
      const name = user ? (user.display_name || user.username || '用户') : '用户';
      const el = document.getElementById('userDisplayName');
      const av = document.getElementById('userAvatar');
      if (el) el.textContent = name;
      if (av) av.textContent = (name[0] || 'U').toUpperCase();
    },

    async _verify() {
      try {
        if (window.apiClient) { await window.apiClient.verifyToken(); this._fillUser(); }
      } catch (e) {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }
    },

    async logout() {
      try { if (window.apiClient) await window.apiClient.logout(); }
      catch (e) { /* ignore */ }
      finally {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('current_user');
        window.location.href = '/login';
      }
    },
  };

  window.Layout = Layout;
})();
