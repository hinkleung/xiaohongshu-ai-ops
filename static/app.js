document.addEventListener('alpine:init', () => {
    Alpine.data('generatorForm', () => ({
        theme: '',
        aiProvider: '',
        images: [],
        previews: [],
        loading: false,
        progress: [],

        handleImages(e) {
            this.images = Array.from(e.target.files);
            this.previews = this.images.map(f => URL.createObjectURL(f));
        },

        async startGenerate() {
            this.loading = true;
            this.progress = [];

            const resp = await fetch('/api/agent/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    theme: this.theme,
                    images: [],
                    ai_provider: this.aiProvider,
                }),
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
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.progress.push(data);
                            this.$nextTick(() => {
                                const log = this.$refs.log;
                                if (log) log.scrollTop = log.scrollHeight;
                            });
                            if (data.node === 'save_draft' && data.status === 'done') {
                                this.loading = false;
                                const draftId = data.data?.draft_id;
                                if (draftId) window.location.href = `/posts/${draftId}`;
                            }
                            if (data.status === 'error') {
                                this.loading = false;
                            }
                        } catch(e) {}
                    }
                }
            }
            this.loading = false;
        },
    }));
});
