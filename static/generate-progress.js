(function() {
'use strict';
var runId = window.location.pathname.split('/').pop();

window.__vue.createPageApp({
    data: function() {
        return { events: [], done: false, error: false, errorMsg: '', draftId: null };
    },
    methods: {
        connect: async function() {
            var self = this;
            // Use regenerate API if runId is a post ID; otherwise generate fresh
            var isRegen = runId && /^\d+$/.test(runId);
            var url = isRegen ? '/api/agent/' + runId + '/regenerate' : '/api/agent/generate';
            var opts = { method: 'POST' };
            if (!isRegen) {
                opts.headers = { 'Content-Type': 'application/json' };
                opts.body = JSON.stringify({ theme: '', images: [], ai_provider: '' });
            }
            var r = await fetch(url, opts);
            var reader = r.body.getReader();
            var decoder = new TextDecoder();
            var buf = '';
            while (true) {
                var rv = await reader.read();
                if (rv.done) break;
                buf += decoder.decode(rv.value, { stream: true });
                var lines = buf.split('\n');
                buf = lines.pop();
                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].slice(0, 6) !== 'data: ') continue;
                    try {
                        var data = JSON.parse(lines[i].slice(6));
                        self.events.push(data);
                        if (data.status === 'error') { self.error = true; self.errorMsg = data.message; }
                        if (data.node === 'save_draft' && data.status === 'done') { self.done = true; self.draftId = data.data && data.data.draft_id; }
                    } catch(_) {}
                }
            }
        }
    },
    mounted: function() { this.connect(); }
});
})();
