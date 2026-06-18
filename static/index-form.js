(function() {
'use strict';
var AGENT_STEPS = [
    { key: 'theme_analyzer', label: '主题解析' },
    { key: 'content_generator', label: '文案生成' },
    { key: 'ai_detector', label: 'AI 痕迹检测' },
    { key: 'humanizer', label: '口语化润色' },
    { key: 'xhs_optimizer', label: '内容优化' },
    { key: 'save_draft', label: '保存草稿' }
];

window.__vue.createPageApp({
    data: function() {
        return {
            theme: '', activityDesc: '', aiProvider: '', images: [], previews: [],
            loading: false, steps: [], doneDraftId: null, showDoneModal: false,
            configs: [], configsFetched: false,
            toastShow: false, toastMessage: '', toastType: 'success'
        };
    },
    computed: {
        filledPercent: function() {
            var done = this.steps.filter(function(s) { return s.status === 'done' || s.status === 'skipped'; }).length;
            return this.steps.length ? Math.round((done / this.steps.length) * 100) : 0;
        },
        currentMessage: function() {
            var running = this.steps.find(function(s) { return s.status === 'running'; });
            if (running) return running.message;
            var last = this.steps[this.steps.length - 1];
            if (last && last.status === 'done') return '全部完成';
            return '';
        }
    },
    methods: {
        updateStep: function(key, patch) {
            var s = this.steps.find(function(x) { return x.key === key; });
            if (s) { for (var k in patch) s[k] = patch[k]; }
        },
        showToast: function(msg, type) {
            this.toastShow = true; this.toastMessage = msg; this.toastType = type || 'success';
        },
        handleImages: function(e) {
            this.images = Array.from(e.target.files);
            this.previews = this.images.map(function(f) { return URL.createObjectURL(f); });
        },
        handleDrop: function(e) {
            var files = Array.from(e.dataTransfer.files).filter(function(f) { return f.type.startsWith('image/'); });
            this.images = this.images.concat(files);
            this.previews = this.images.map(function(f) { return f instanceof File ? URL.createObjectURL(f) : f; });
        },
        startGenerate: async function() {
            var self = this;
            self.loading = true; self.showDoneModal = false; self.doneDraftId = null;
            self.steps = AGENT_STEPS.map(function(s) { return { key: s.key, label: s.label, status: 'pending', message: '' }; });
            var imageUrls = [];
            if (self.images.length > 0) {
                var upKey = '_upload';
                self.steps.unshift({ key: upKey, label: '上传图片', status: 'running', message: '' });
                var fd = new FormData();
                self.images.forEach(function(f) { fd.append('files', f); });
                try {
                    var ur = await fetch('/api/upload', { method: 'POST', body: fd });
                    var ud = await ur.json();
                    imageUrls = ud.urls || [];
                    self.updateStep(upKey, { status: 'done', message: '上传完成 (' + imageUrls.length + ' 张)' });
                } catch(e) {
                    self.updateStep(upKey, { status: 'error', message: '上传失败' });
                    self.loading = false; return;
                }
            }
            try {
                var resp = await fetch('/api/agent/generate', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme: self.theme, activity_description: self.activityDesc, images: imageUrls, ai_provider: self.aiProvider })
                });
                var reader = resp.body.getReader();
                var decoder = new TextDecoder();
                var buffer = '';
                while (true) {
                    var rv = await reader.read();
                    if (rv.done) break;
                    buffer += decoder.decode(rv.value, { stream: true });
                    var lines = buffer.split('\n');
                    buffer = lines.pop();
                    for (var i = 0; i < lines.length; i++) {
                        if (lines[i].slice(0, 6) !== 'data: ') continue;
                        try {
                            var data = JSON.parse(lines[i].slice(6));
                            var st = data.status;
                            if (st === 'done' && data.message && data.message.indexOf('跳过') >= 0) st = 'skipped';
                            self.updateStep(data.node, { status: st, message: data.message || '' });
                            if (data.node === 'save_draft' && st === 'done') self.doneDraftId = data.data && data.data.draft_id;
                            if (st === 'error') { self.loading = false; return; }
                        } catch(_) {}
                    }
                }
            } catch(e) {
                var rn = self.steps.find(function(s) { return s.status === 'running'; });
                if (rn) self.updateStep(rn.key, { status: 'error', message: String(e.message || e) });
            }
            self.loading = false;
            var allDone = self.steps.every(function(s) { return s.status === 'done' || s.status === 'skipped'; });
            if (allDone && self.doneDraftId) self.showDoneModal = true;
        },
        closeDoneModal: function() { this.showDoneModal = false; },
        goToPost: function() { if (this.doneDraftId) window.location.href = '/posts/' + this.doneDraftId; },
        stayAndReset: function() {
            this.showDoneModal = false; this.theme = ''; this.activityDesc = ''; this.images = []; this.previews = [];
            this.steps = []; this.doneDraftId = null;
        }
    },
    mounted: function() {
        // Use server-preloaded data first (instant), refresh in background
        var pd = window.__vue.getPageData();
        if (pd.configs && pd.configs.length) {
            this.configs = pd.configs; this.configsFetched = true;
        }
        var self = this;
        fetch('/api/configs/ai').then(function(r) { return r.json(); }).then(function(d) {
            self.configs = d || []; self.configsFetched = true;
        });
    }
});
})();
