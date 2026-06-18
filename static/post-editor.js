(function() {
'use strict';
var CL = window.__vue.calcTitleLength;
var postId = parseInt(window.location.pathname.split('/').pop()) || 0;

window.__vue.createPageApp({
    data: function() {
        return {
            post: null, loading: true, error: '',
            uploading: false, titleErr: '', contentErr: '', imagesErr: '',
            showActivity: false, showRepublishModal: false, showLightbox: false, lightboxSrc: '',
            toastShow: false, toastMessage: '', toastType: 'success'
        };
    },
    computed: {
        titleCount: function() {
            return '(' + CL(this.post && this.post.title || '') + '/20)';
        }
    },
    methods: {
        checkTitle: function() {
            var t = (this.post && this.post.title || '').trim();
            if (!t) { this.titleErr = '标题不能为空'; return; }
            if (CL(t) > 20) { this.titleErr = '标题超长（小红书限制 20 个字/英文词），当前' + CL(t); return; }
            this.titleErr = '';
        },
        checkContent: function() {
            if (!(this.post && this.post.content || '').trim()) { this.contentErr = '正文不能为空'; return; }
            this.contentErr = '';
        },
        showToast: function(msg, type) {
            this.toastShow = true; this.toastMessage = msg; this.toastType = type || 'success';
        },
        uploadImages: async function(e) {
            var files = e.target.files;
            if (!files.length) return;
            this.uploading = true;
            var fd = new FormData();
            for (var i = 0; i < files.length; i++) fd.append('files', files[i]);
            try {
                var r = await fetch('/api/upload', { method: 'POST', body: fd });
                var d = await r.json();
                if (d.urls) this.post.images = (this.post.images || []).concat(d.urls);
                this.imagesErr = '';
            } catch(ex) { this.showToast('图片上传失败: ' + ex.message, 'error'); }
            this.uploading = false;
            e.target.value = '';
        },
        openLightbox: function(url) { this.lightboxSrc = url; this.showLightbox = true; },
        removeImage: function(i) { this.post.images.splice(i, 1); },
        addTag: function(e) {
            var t = e.target.value.trim();
            if (t && !this.post.tags.includes(t)) this.post.tags.push(t);
            e.target.value = '';
        },
        removeTag: function(i) { this.post.tags.splice(i, 1); },
        save: async function() {
            var r = await fetch('/api/posts/' + this.post.id, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: this.post.title, content: this.post.content, tags: this.post.tags, images: this.post.images })
            });
            this.showToast(r.ok ? '已保存' : '保存失败', r.ok ? 'success' : 'error');
        },
        doPublish: async function() {
            if (this.post.status === 'published') return;
            this.checkTitle(); this.checkContent();
            if (!(this.post.images || []).length) this.imagesErr = '小红书发布至少需要 1 张图片，请先上传';
            else this.imagesErr = '';
            if (this.titleErr || this.contentErr || this.imagesErr) { this.showToast('请先修正上方标注的问题再发布', 'error'); return; }
            try {
                await fetch('/api/posts/' + this.post.id, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: this.post.title, content: this.post.content, tags: this.post.tags, images: this.post.images })
                });
                var r = await fetch('/api/agent/' + this.post.id + '/publish', { method: 'POST' });
                var d = await r.json();
                if (d.success) {
                    this.post.status = 'publishing';
                    this.showToast('⏳ 发布任务已提交，请稍候…');
                    this.pollStatus();
                } else {
                    this.showToast('❌ ' + (d.error || '发布失败'), 'error');
                }
            } catch(ex) { this.showToast('❌ 网络错误: ' + ex.message, 'error'); }
        },
        pollStatus: function() {
            var self = this, attempts = 0, max = 40;
            var timer = setInterval(async function() {
                attempts++;
                if (attempts > max || self.post.status !== 'publishing') { clearInterval(timer); return; }
                try {
                    var r = await fetch('/api/posts/' + self.post.id);
                    var p = await r.json();
                    if (p.status === 'published') { self.post.status = 'published'; self.showToast('✅ 发布成功！'); clearInterval(timer); }
                    else if (p.status === 'failed') { self.post.status = 'failed'; self.showToast('❌ 发布失败，可修改后重试', 'error'); clearInterval(timer); }
                } catch(_) {}
            }, 3000);
        },
        confirmRepublish: function() {
            this.showRepublishModal = false;
            this.doPublish();
        },
    },
    mounted: function() {
        var self = this;
        // Use server-preloaded data first (instant)
        var pd = window.__vue.getPageData();
        if (pd.post) { self.post = pd.post; self.loading = false; self.checkTitle(); }
        // Refresh in background
        if (!postId) { if (!pd.post) { self.loading = false; self.error = '无效的文章 ID'; } return; }
        fetch('/api/posts/' + postId).then(function(r) {
            if (!r.ok) throw new Error('Not found');
            return r.json();
        }).then(function(d) {
            self.post = d; self.loading = false; self.checkTitle();
        }).catch(function(e) {
            if (!pd.post) { self.loading = false; self.post = null; self.error = '文章加载失败'; }
        });
    }
});
})();
