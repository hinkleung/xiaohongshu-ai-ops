(function() {
'use strict';

window.__vue.createPageApp({
    data: function() {
        return {
            filter: '', posts: [], loading: true,
            showDeleteModal: false, deleteTargetId: null,
            toastShow: false, toastMessage: '', toastType: 'success'
        };
    },
    computed: {
        filteredPosts: function() {
            // Local filter for instant display — refreshed from API on tab switch
            return this.filter ? this.posts.filter(function(p) { return p.status === this.filter; }.bind(this)) : this.posts;
        }
    },
    watch: {
        filter: function(newVal) {
            this.fetchPosts(newVal);
        }
    },
    methods: {
        goDetail: function(id) { window.location.href = '/posts/' + id; },
        showToast: function(msg, type) {
            this.toastShow = true; this.toastMessage = msg; this.toastType = type || 'success';
        },
        fetchPosts: async function(status) {
            var self = this;
            self.loading = true;
            try {
                var url = '/api/posts';
                if (status) url += '?status=' + encodeURIComponent(status);
                var r = await fetch(url); self.posts = await r.json();
                // Passive sync: cross-check publishing posts
                var pub = self.posts.filter(function(p) { return p.status === 'publishing'; });
                if (pub.length > 0) {
                    fetch('/api/posts/sync-publishing', { method: 'POST' }).then(function(r2) { return r2.json(); }).then(function(d) {
                        if (d.updated > 0) self.fetchPosts(self.filter);
                    });
                }
            } catch(_) {}
            self.loading = false;
        },
        deletePost: function(id) {
            this.deleteTargetId = id; this.showDeleteModal = true;
        },
        confirmDelete: async function() {
            var id = this.deleteTargetId;
            this.showDeleteModal = false; this.deleteTargetId = null;
            await fetch('/api/posts/' + id, { method: 'DELETE' });
            this.posts = this.posts.filter(function(p) { return p.id !== id; });
            this.showToast('已删除');
        }
    },
    mounted: function() {
        var pd = window.__vue.getPageData();
        if (pd.posts) { this.posts = pd.posts; this.loading = false; }
        // Initial fetch (all posts) + sync-publishing
        this.fetchPosts();
    }
});
})();
