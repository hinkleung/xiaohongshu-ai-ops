const AGENT_STEPS = [
    {key: 'theme_analyzer', label: '主题解析'},
    {key: 'content_generator', label: '文案生成'},
    {key: 'ai_detector', label: 'AI 痕迹检测'},
    {key: 'humanizer', label: '口语化润色'},
    {key: 'xhs_optimizer', label: '内容优化'},
    {key: 'save_draft', label: '保存草稿'},
];

document.addEventListener('alpine:init', () => {
    Alpine.data('generatorForm', () => ({
        theme: '', aiProvider: '', images: [], previews: [],
        loading: false, steps: [], doneDraftId: null, showDoneModal: false,

        // ── Patch one step immutably (returns new array) ──
        _patchStep(key, patch) {
            this.steps = this.steps.map(function(s) {
                if (s.key === key) {
                    var merged = {};
                    var k;
                    for (k in s) merged[k] = s[k];
                    for (k in patch) merged[k] = patch[k];
                    return merged;
                }
                return s;
            });
        },

        handleImages(e) {
            this.images = Array.from(e.target.files);
            this.previews = this.images.map(f => URL.createObjectURL(f));
        },

        handleDrop(e) {
            const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            this.images = [...this.images, ...files];
            this.previews = this.images.map(f => f instanceof File ? URL.createObjectURL(f) : f);
        },

        async startGenerate() {
            this.loading = true;
            this.showDoneModal = false;
            this.doneDraftId = null;
            // Init all steps as pending
            this.steps = AGENT_STEPS.map(function(s) {
                return {key: s.key, label: s.label, status: 'pending'};
            });

            // Upload images first if selected
            var imageUrls = [];
            if (this.images.length > 0) {
                var upKey = '_upload';
                this.steps = [{key: upKey, label: '上传图片', status: 'running'}].concat(this.steps);
                var fd = new FormData();
                this.images.forEach(function(f) { fd.append('files', f); });
                try {
                    var upResp = await fetch('/api/upload', {method: 'POST', body: fd});
                    var upData = await upResp.json();
                    imageUrls = upData.urls || [];
                    this._patchStep(upKey, {status: 'done', message: '上传完成 (' + imageUrls.length + ' 张)'});
                } catch(e) {
                    this._patchStep(upKey, {status: 'error', message: '上传失败'});
                    this.loading = false;
                    return;
                }
            }

            try {
                const resp = await fetch('/api/agent/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ theme: this.theme, images: imageUrls, ai_provider: this.aiProvider }),
                });
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const {done, value} = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, {stream: true});
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    for (let i = 0; i < lines.length; i++) {
                        var line = lines[i];
                        if (line.slice(0, 6) !== 'data: ') continue;
                        try {
                            const data = JSON.parse(line.slice(6));
                            var status = data.status;
                            // Mark as skipped if message says so
                            if (status === 'done' && data.message && data.message.indexOf('跳过') >= 0) {
                                status = 'skipped';
                            }
                            this._patchStep(data.node, {
                                status: status,
                                message: data.message || '',
                                data: data.data,
                            });

                            if (data.node === 'save_draft' && status === 'done') {
                                this.doneDraftId = data.data && data.data.draft_id;
                            }
                            if (status === 'error') {
                                this.loading = false;
                                return;
                            }
                        } catch(e) { /* skip malformed SSE */ }
                    }
                }
            } catch(e) {
                // Find first running step and mark it error
                for (var j = 0; j < this.steps.length; j++) {
                    if (this.steps[j].status === 'running') {
                        this._patchStep(this.steps[j].key, {status: 'error', message: String(e.message || e)});
                        break;
                    }
                }
            }
            this.loading = false;

            // Check all steps completed → show success modal
            var allDone = true;
            for (var k = 0; k < this.steps.length; k++) {
                var s = this.steps[k];
                if (s.status !== 'done' && s.status !== 'skipped') { allDone = false; break; }
            }
            if (allDone && this.doneDraftId) {
                this.showDoneModal = true;
            }
        },

        closeDoneModal() { this.showDoneModal = false; },
        goToPost() {
            if (this.doneDraftId) window.location.href = '/posts/' + this.doneDraftId;
        },
        stayAndReset() {
            this.showDoneModal = false;
            this.theme = ''; this.images = []; this.previews = [];
            this.steps = []; this.doneDraftId = null;
        },
    }));
});
