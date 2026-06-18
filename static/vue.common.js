// vue.common.js — Shared Vue 3 infrastructure for all pages
// Loaded after Vue CDN, before page-specific scripts
(function() {
'use strict';

const { createApp } = Vue;

// ── Helpers ──────────────────────────────────────

function getPageData() {
    var el = document.getElementById('page-data');
    if (!el) return {};
    try { return JSON.parse(el.textContent); } catch(e) { return {}; }
}

function calcTitleLength(s) {
    var byteLen = 0;
    for (var i = 0; i < (s || '').length; i++) {
        byteLen += s.charCodeAt(i) > 127 ? 2 : 1;
    }
    return Math.floor((byteLen + 1) / 2);
}

// ── AppToast ─────────────────────────────────────

var AppToast = {
    props: {
        show: Boolean,
        message: String,
        type: { type: String, default: 'success' },
        duration: { type: Number, default: 2500 }
    },
    emits: ['close'],
    created: function() {
        var self = this;
        this._watchShow = function(val) {
            if (val && self.duration > 0) {
                setTimeout(function() { self.$emit('close'); }, self.duration);
            }
        };
    },
    watch: {
        show: function(val) { if (this._watchShow) this._watchShow(val); }
    },
    template: '<div v-if="show" :style="\'position:fixed;top:20px;right:20px;max-width:380px;z-index:9999;background:\' + (type === \'error\' ? \'var(--error)\' : \'var(--success)\') + \';color:#fff;padding:10px 20px;border-radius:12px;font-size:.85rem;animation:up .3s ease-out;word-break:break-all;box-shadow:0 4px 20px rgba(0,0,0,.15);\'">{{ message }}</div>'
};

// ── AppConfirmModal ──────────────────────────────

var AppConfirmModal = {
    props: {
        show: Boolean,
        title: { type: String, default: '确认' },
        message: { type: String, default: '确定吗？' },
        confirmText: { type: String, default: '确认' },
        cancelText: { type: String, default: '取消' },
        danger: Boolean
    },
    emits: ['confirm', 'update:show'],
    mounted: function() {
        var self = this;
        this.__onKey = function(e) { if (e.key === 'Escape') self.cancel(); };
        document.addEventListener('keydown', this.__onKey);
    },
    beforeUnmount: function() {
        if (this.__onKey) document.removeEventListener('keydown', this.__onKey);
    },
    methods: {
        confirm: function() { this.$emit('confirm'); },
        cancel: function() { this.$emit('update:show', false); },
        backdrop: function() { this.$emit('update:show', false); }
    },
    template: '<div v-if="show" style="position:fixed;inset:0;z-index:1001;background:rgba(0,0,0,.35);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);display:flex;align-items:center;justify-content:center;" @click.self="backdrop">' +
        '<div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;padding:28px;max-width:340px;width:90%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.15);">' +
            '<h3 style="margin-bottom:10px;font-size:1.1rem;">{{ title }}</h3>' +
            '<p style="color:var(--text-secondary);font-size:.88rem;margin-bottom:20px;">{{ message }}</p>' +
            '<div style="display:flex;gap:10px;justify-content:center;">' +
                '<button @click="cancel" class="btn btn-outline">{{ cancelText }}</button>' +
                '<button @click="confirm" :class="\'btn \' + (danger ? \'btn-danger\' : \'btn-primary\')">{{ confirmText }}</button>' +
            '</div>' +
        '</div>' +
    '</div>'
};

// ── AppBadge ─────────────────────────────────────

var AppBadge = {
    props: { status: String },
    computed: {
        label: function() {
            return { draft: '草稿', publishing: '发布中', published: '已发布', failed: '发布失败' }[this.status] || this.status;
        }
    },
    template: '<span :class="\'badge badge-\' + status">{{ label }}</span>'
};

// ── AppLightbox ──────────────────────────────────

var AppLightbox = {
    props: { show: Boolean, src: String },
    emits: ['close'],
    mounted: function() {
        var self = this;
        this.__onKey = function(e) { if (e.key === 'Escape') self.$emit('close'); };
        document.addEventListener('keydown', this.__onKey);
    },
    beforeUnmount: function() {
        if (this.__onKey) document.removeEventListener('keydown', this.__onKey);
    },
    methods: {
        dismiss: function() { this.$emit('close'); }
    },
    template: '<div v-if="show" style="position:fixed;inset:0;z-index:2000;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;" @click="dismiss">' +
        '<img :src="src" style="max-width:92vw;max-height:90vh;object-fit:contain;border-radius:8px;box-shadow:0 4px 40px rgba(0,0,0,.3);">' +
    '</div>'
};

// ── Factory ──────────────────────────────────────

function createPageApp(options) {
    var app = createApp(options);
    app.component('AppToast', AppToast);
    app.component('AppConfirmModal', AppConfirmModal);
    app.component('AppBadge', AppBadge);
    app.component('AppLightbox', AppLightbox);
    return app.mount('#app');
}

// ── Expose ───────────────────────────────────────

window.__vue = { getPageData: getPageData, calcTitleLength: calcTitleLength, createPageApp: createPageApp };

})();
