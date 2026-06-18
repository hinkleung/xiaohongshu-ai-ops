(function() {
'use strict';

var CACHE_KEY = 'xhs_login_cache';
var CACHE_TTL = 30 * 60 * 1000;

function readCache() {
    try { var d = JSON.parse(localStorage.getItem(CACHE_KEY)); if (d && d.ts && (Date.now() - d.ts < CACHE_TTL)) return d; } catch(_) {}
    return null;
}
function writeCache(data) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), status: data.status || data, profile: data.profile || null })); } catch(_) {}
}
function clearCache() { try { localStorage.removeItem(CACHE_KEY); } catch(_) {} }

function parseTimeout(t) {
    var m = t.match(/(\d+)m/), s = t.match(/(\d+)s/);
    return (m ? parseInt(m[1]) * 60 : 0) + (s ? parseInt(s[1]) : 0);
}
function formatCountdown(sec) { return Math.floor(sec / 60) + '分' + (sec % 60) + '秒'; }

var cached = readCache();

window.__vue.createPageApp({
    data: function() {
        return {
            // AI Config
            configs: [], loadingConfigs: true,
            form: { provider: '', api_key: '', api_base: '', model: '' },
            showDeleteConfigModal: false, deleteConfigTargetId: null,

            // XHS Status
            xhsStatus: cached ? (cached.status || {}) : {},
            xhsProfile: cached ? cached.profile : null,
            xhsLoading: !cached,
            xhsLoadingProfile: false,

            // QR
            showQR: false, qrLoading: false, qrImage: '', qrExpireText: '', qrTimer: null, qrError: '',

            // Logout
            showLogoutModal: false,

            // Toast
            toastShow: false, toastMessage: '', toastType: 'success'
        };
    },
    methods: {
        showToast: function(msg, type) {
            this.toastShow = true; this.toastMessage = msg; this.toastType = type || 'success';
        },
        fetchConfigs: async function() {
            try { var r = await fetch('/api/configs/ai'); this.configs = await r.json(); } catch(_) {}
            this.loadingConfigs = false;
        },
        addConfig: async function() {
            var r = await fetch('/api/configs/ai', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.form)
            });
            if (r.ok) {
                this.configs.push(await r.json());
                this.form = { provider: '', api_key: '', api_base: '', model: '' };
                var panel = document.getElementById('add-provider-panel');
                if (panel) panel.open = false;
                this.showToast('配置已添加');
            } else { this.showToast('添加失败', 'error'); }
        },
        activate: async function(id) {
            await fetch('/api/configs/ai/' + id + '/activate', { method: 'POST' });
            this.configs.forEach(function(c) { c.is_active = c.id === id; });
            this.showToast('已启用');
        },
        deleteConfig: function(id) {
            this.deleteConfigTargetId = id; this.showDeleteConfigModal = true;
        },
        confirmDeleteConfig: async function() {
            var id = this.deleteConfigTargetId;
            this.showDeleteConfigModal = false; this.deleteConfigTargetId = null;
            await fetch('/api/configs/ai/' + id, { method: 'DELETE' });
            await this.fetchConfigs();
            this.showToast('已删除');
        },

        // ── XHS ──
        checkXhsStatus: async function(poll, silent) {
            if (!silent) this.xhsLoading = true;
            var maxRetries = poll ? 3 : 1, delay = 1500;
            var result = { is_logged_in: false };
            for (var i = 0; i < maxRetries; i++) {
                try { var r = await fetch('/api/xhs/status'); result = await r.json(); } catch(_) {}
                if (result && result.is_logged_in) break;
                if (i < maxRetries - 1) await new Promise(function(res) { setTimeout(res, delay); });
            }
            var wasLoggedIn = this.xhsStatus && this.xhsStatus.is_logged_in;
            this.xhsStatus = result;
            if (result && result.is_logged_in) {
                // Always refresh profile on manual refresh, only if missing on silent
                if (!silent || !wasLoggedIn || !this.xhsProfile) await this.fetchXhsProfile();
                if (this.xhsProfile) writeCache({ status: result, profile: this.xhsProfile });
                else writeCache({ status: result, profile: null });
            } else { clearCache(); this.xhsProfile = null; }
            this.xhsLoading = false;
        },
        fetchXhsProfile: async function() {
            this.xhsLoadingProfile = true;
            try {
                var r = await fetch('/api/xhs/me');
                this.xhsProfile = await r.json();
                writeCache({ status: this.xhsStatus, profile: this.xhsProfile });
            } catch(_) { this.xhsProfile = null; }
            this.xhsLoadingProfile = false;
        },

        // ── QR ──
        openQR: function() {
            this.showQR = true; this.qrLoading = true; this.qrImage = ''; this.qrExpireText = ''; this.qrError = '';
            if (this.qrTimer) clearInterval(this.qrTimer);
            this.fetchQR();
        },
        refreshQR: function() {
            this.qrLoading = true; this.qrImage = ''; this.qrExpireText = ''; this.qrError = '';
            if (this.qrTimer) clearInterval(this.qrTimer);
            this.fetchQR();
        },
        fetchQR: async function() {
            try {
                var r = await fetch('/api/xhs/login', { method: 'POST' });
                var d = await r.json();
                this.qrImage = d.img; this.qrLoading = false;
                if (d.timeout) {
                    var self = this, sec = parseTimeout(d.timeout);
                    if (sec > 0) {
                        self.qrExpireText = '二维码 ' + formatCountdown(sec) + ' 后过期';
                        self.qrTimer = setInterval(function() {
                            sec--;
                            if (sec <= 0) { clearInterval(self.qrTimer); self.qrExpireText = '二维码已过期，请重新获取'; }
                            else { self.qrExpireText = '二维码 ' + formatCountdown(sec) + ' 后过期'; }
                        }, 1000);
                    }
                }
            } catch(e) { this.qrLoading = false; this.qrError = '获取失败，请重试'; }
        },
        closeQR: function() {
            this.showQR = false;
            if (this.qrTimer) clearInterval(this.qrTimer);
            var self = this;
            setTimeout(function() { self.checkXhsStatus(true); }, 2000);
        },

        // ── Logout ──
        doLogout: async function() {
            this.showLogoutModal = false;
            await fetch('/api/xhs/logout', { method: 'DELETE' });
            clearCache();
            this.xhsStatus = { is_logged_in: false };
            this.xhsProfile = null;
            this.showToast('已退出登录');
        }
    },
    mounted: function() {
        // Use server-preloaded data first (instant)
        var pd = window.__vue.getPageData();
        if (pd.configs && pd.configs.length) { this.configs = pd.configs; this.loadingConfigs = false; }
        this.fetchConfigs(); // refresh in background
        if (!cached) this.checkXhsStatus();
    }
});
})();
