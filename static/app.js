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
        loading: false, steps: AGENT_STEPS.map(s => ({...s, status: 'pending'})),

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
            this.steps = AGENT_STEPS.map(s => ({...s, status: 'pending'}));

            // Show upload step if images selected
            var imageUrls = [];
            if (this.images.length > 0) {
                var uploadStep = {key: '_upload', label: '上传图片', status: 'running', message: '上传中...'};
                this.steps.unshift(uploadStep);
                var formData = new FormData();
                this.images.forEach(function(f) { formData.append('files', f); });
                var upResp = await fetch('/api/upload', {method: 'POST', body: formData});
                var upData = await upResp.json();
                imageUrls = upData.urls || [];
                uploadStep.status = 'done';
                uploadStep.message = '上传完成 (' + imageUrls.length + ' 张)';
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
                    for (const line of lines) {
                        if (!line.startsWith('data: ')) continue;
                        try {
                            const data = JSON.parse(line.slice(6));
                            const step = this.steps.find(s => s.key === data.node);
                            if (step) {
                                step.status = data.status;
                                step.message = data.message;
                                step.data = data.data;
                                // Mark as skipped if the message indicates it was skipped
                                if (data.status === 'done' && data.message && data.message.includes('跳过')) {
                                    step.status = 'skipped';
                                }
                            }
                            if (data.node === 'save_draft' && data.status === 'done') {
                                const id = data.data?.draft_id;
                                if (id) {
                                    // Brief delay so user sees the completed steps
                                    setTimeout(() => { window.location.href = `/posts/${id}`; }, 600);
                                    return;
                                }
                            }
                            if (data.status === 'error') {
                                this.loading = false;
                                return;
                            }
                        } catch(e) { /* skip malformed SSE lines */ }
                    }
                }
            } catch(e) {
                const step = this.steps.find(s => s.status === 'running');
                if (step) { step.status = 'error'; step.message = e.message; }
            }
            this.loading = false;
        },
    }));
});
